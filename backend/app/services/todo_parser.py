"""Todo extraction: parse arbitrary text/file into structured todo candidates (AI-02, AI-04, AI-06).

The agent parses user input (text or extracted file content) into todo candidates with:
title (event), date, time, location, notes. Some fields may be null.
Candidates are returned for manual confirmation before being saved.

In demo mode (no LLM), uses rule-based extraction for dates, times, locations,
and multi-item splitting so the feature works without an external model.
"""

import json
import re
from datetime import datetime, timedelta, timezone
from typing import List

from app.core.config import settings
from app.core.response import ApiError
from app.services.model import ModelError, chat_completion, validate_output

TODO_SCHEMA = {
    "type": "object",
    "required": ["todos"],
    "properties": {
        "todos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "date": {"type": "string"},
                    "time": {"type": "string"},
                    "location": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["title"],
            },
        }
    },
}

TODO_PROMPT = """你是一个待办事项解析助手。用户会输入任意自然语言文本（可能包含多个待办），请从中提取结构化的待办事项。

【输出要求】
只输出一个 JSON 对象，不要输出任何解释、markdown 代码块标记或额外文字。JSON 结构如下：
{
  "todos": [
    {
      "title": "事件名称（简短，必填）",
      "date": "日期，格式 YYYY-MM-DD；无法判断则为 null",
      "time": "时间，格式 HH:MM（24小时制，如 19:00）；无法判断则为 null",
      "location": "地点；无法判断则为 null",
      "notes": "注意事项；无法判断则为 null"
    }
  ]
}

【解析规则】
- 时间：支持中文（如"七点"="07:00"、"下午三点"="15:00"、"晚上8点半"="20:30"）和数字格式（如"19:00"、"7pm"）
- 日期：支持"今天"、"明天"、"下周三"、"12月25日"等相对和绝对日期
- 多事项：用逗号、句号、分号、换行或"然后"、"还有"等连接的多个事项要拆分为多个 todo
- 地点：通常跟在"在"、"位于"、"地点"、"去"等词后面
- 如果某字段无法从文本中判断，填 null，不要编造
- 重要：输入中的每个独立事项都必须输出，不得合并、遗漏或省略

【示例】

输入：明天上午十点在会议室A开项目评审会，记得带PPT
输出：
{"todos":[{"title":"项目评审会","date":"2024-01-02","time":"10:00","location":"会议室A","notes":"带PPT"}]}

输入：下周三下午3点交报告，然后晚上8点和朋友吃饭，周六全天复习考试
输出：
{"todos":[{"title":"交报告","date":null,"time":"15:00","location":null,"notes":null},{"title":"和朋友吃饭","date":null,"time":"20:00","location":null,"notes":null},{"title":"复习考试","date":null,"time":null,"location":null,"notes":"全天"}]}

输入：买牛奶
输出：
{"todos":[{"title":"买牛奶","date":null,"time":null,"location":null,"notes":null}]}"""


class ParseError(ApiError):
    def __init__(self, message: str):
        super().__init__(code="BUSINESS_RULE", message=message)


async def parse_todos(
    text: str,
    llm_config: dict | None = None,
) -> dict:
    """Parse text into structured todo candidates (not saved).

    Returns dict with:
      - candidates: list of parsed todo dicts
      - parser: "llm" if an LLM was used, "rule" if rule-based fallback

    llm_config may contain api_key, base_url, model to override global
    settings. When no LLM is available (neither global nor per-request),
    falls back to rule-based extraction.
    """
    if not text or not text.strip():
        raise ParseError("empty input")

    cfg = llm_config or {}
    api_key = (cfg.get("api_key") or "").strip()
    base_url = (cfg.get("base_url") or "").strip()
    model = (cfg.get("model") or "").strip()

    has_llm = bool(api_key and base_url and model) or not settings.is_demo_mode
    parser_used = "rule"

    if not has_llm:
        raw_todos = _demo_parse(text)
    else:
        try:
            raw = await chat_completion(
                system_prompt=TODO_PROMPT,
                user_content=text,
                response_schema=TODO_SCHEMA,
                api_key=api_key,
                base_url=base_url,
                model=model,
            )
            data = _extract_json(raw)
            validated = validate_output(data, TODO_SCHEMA)
            raw_todos = validated.get("todos", [])
            parser_used = "llm"
            # Fallback: LLM returned no todos but input likely has multiple items
            if not raw_todos and _has_multiple_segments(text):
                raw_todos = _demo_parse(text)
                parser_used = "rule"
        except (json.JSONDecodeError, ValueError, ModelError):
            # LLM output invalid or call failed: fall back to rule-based parsing
            raw_todos = _demo_parse(text)
            parser_used = "rule"

    result = []
    for item in raw_todos:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        date_str = item.get("date")
        time_str = item.get("time")
        due_at = _combine_datetime(date_str, time_str)
        result.append(
            {
                "title": title,
                "due_at": due_at,
                "location": _clean(item.get("location")),
                "notes": _clean(item.get("notes")),
            }
        )
    return {"candidates": result, "parser": parser_used}


def _extract_json(raw: str) -> dict:
    """Extract a JSON object from LLM output, handling code fences and extra text."""
    s = raw.strip()
    # Strip markdown code fences
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    # Find the first JSON object
    start = s.find("{")
    if start == -1:
        raise ValueError("no JSON object found")
    # Try parsing from the start; if it fails, attempt to find matching braces
    try:
        return json.loads(s[start:])
    except json.JSONDecodeError:
        depth = 0
        for i in range(start, len(s)):
            if s[i] == "{":
                depth += 1
            elif s[i] == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(s[start : i + 1])
        raise ValueError("no matching closing brace")


# ---------------------------------------------------------------------------
# Demo mode: rule-based parser
# ---------------------------------------------------------------------------

# Split text into multiple todo items by common separators
_ITEM_SPLIT_RE = re.compile(r"[，。；、\n;]+|然后|接着|另外|还有|以及")

# Date patterns
_DATE_PATTERNS = [
    # 今天, 今日, 明天, 明日, 后天
    (re.compile(r"(今天|今日|明天|明日|后天)"), "_relative_day"),
    # English: today, tomorrow, the day after tomorrow
    (re.compile(r"\b(the day after tomorrow|tomorrow|today)\b", re.IGNORECASE), "_en_relative_day"),
    # 下周一/下周一/下星期一 ... 下周日
    (re.compile(r"下(?:周|星期|礼拜)([一二三四五六日天])"), "_next_weekday"),
    # English: next Monday/Tuesday/...
    (re.compile(r"\bnext\s+(mon|tue|wed|thu|fri|sat|sun)\w*\b", re.IGNORECASE), "_en_next_weekday"),
    # 本周一/周X/星期X (this week)
    (re.compile(r"(?:本)?(?:周|星期|礼拜)([一二三四五六日天])"), "_this_weekday"),
    # English: this Monday (same week)
    (re.compile(r"\bthis\s+(mon|tue|wed|thu|fri|sat|sun)\w*\b", re.IGNORECASE), "_en_this_weekday"),
    # X月X日
    (re.compile(r"(\d{1,2})月(\d{1,2})日?"), "_month_day"),
    # English: December 25 / Dec 25 / 25 December
    (re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+(\d{1,2})\b", re.IGNORECASE), "_en_month_day"),
    (re.compile(r"\b(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\b", re.IGNORECASE), "_en_day_month"),
    # MM-DD or MM/DD
    (re.compile(r"(\d{1,2})[-/](\d{1,2})"), "_month_day"),
]

_EN_WEEKDAY_MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
_EN_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# Chinese numeral map for time parsing
_CN_NUM_MAP = {
    "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "十一": 11, "十二": 12,
}


def _cn_num_to_int(s: str) -> int | None:
    """Convert Chinese numeral string to int. Returns None if not a numeral."""
    if s in _CN_NUM_MAP:
        return _CN_NUM_MAP[s]
    if len(s) == 2 and s[0] == "十":
        return 10 + _CN_NUM_MAP.get(s[1], 0)
    return None


# Time patterns
_TIME_PATTERNS = [
    # 上午/下午/晚上/中午 X点(X分) - Arabic numerals
    (re.compile(r"(上午|下午|晚上|中午|早上|凌晨|早晨)?\s*(\d{1,2})点(?:(\d{1,2})分|半)?"), "_cn_time"),
    # 上午/下午/晚上 X点 - Chinese numerals (e.g. 七点, 下午三点半)
    (re.compile(r"(上午|下午|晚上|中午|早上|凌晨|早晨)?\s*([一二两三四五六七八九十]{1,2})点(?:半)?"), "_cn_char_time"),
    # English: 3pm / 3 am / 3:30pm / 15:00
    (re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", re.IGNORECASE), "_en_ampm_time"),
    # HH:MM or HH:MM:SS (24h)
    (re.compile(r"\b(\d{1,2}):(\d{2})(?::\d{2})?\b"), "_hmm_time"),
]

# Location pattern: 在...(地点), 地点..., 于..., 去X(出差/旅行)
# Stop at common action verbs to avoid capturing the whole sentence
_LOCATION_STOP_VERBS = r"(?:开|去|做|参加|召开|举办|进行|举行|吃|喝|见|找|等|拿|带|买|卖|写|读|看|听|说|聊|走|跑|飞|坐|开|上|下|回|出|进|到|往|向|从|由|讨论|商量|研究|处理|准备|安排|复习|学习|工作|加班|出差|旅游|旅行|拜访|约会|聚餐|吃饭|睡觉|起床|运动|健身|游泳|跑步|打球|看电影|看剧|购物|逛街|打扫|整理|洗衣|做饭)"

_LOCATION_PATTERNS = [
    # 在[地点] + verb/punctuation
    re.compile(r"在([\u4e00-\u9fa5A-Za-z0-9_\-]{2,20}?)(?=" + _LOCATION_STOP_VERBS + r"|[，。；、\n]|$)"),
    # 地点：[地点]
    re.compile(r"地点[：:]?\s*([\u4e00-\u9fa5A-Za-z0-9_\-]{2,20}?)(?:[，。；、\n]|$)"),
    # 出差去[地点] / 去[地点]出差
    re.compile(r"(?:出差)?去([\u4e00-\u9fa5A-Za-z0-9_\-]{2,20}?)(?:出差|$|[，。；、\n])"),
    # English: in/at [Room/Place] - match capitalized place names or "Room X"
    re.compile(r"\b(?:in|at)\s+((?:Room\s+\w+|[A-Z][A-Za-z0-9_\-]*(?:\s+[A-Z][A-Za-z0-9_\-]*)*))"),
]

_WEEKDAY_MAP = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}


def _has_multiple_segments(text: str) -> bool:
    """Check if input text likely contains multiple todo items.

    Uses the same split regex as _demo_parse to detect multiple segments.
    """
    segments = [s.strip() for s in _ITEM_SPLIT_RE.split(text) if s.strip()]
    return len(segments) > 1


def _demo_parse(text: str) -> List[dict]:
    """Rule-based todo parser for demo mode."""
    items = _ITEM_SPLIT_RE.split(text)
    todos = []
    for item in items:
        item = item.strip()
        if not item:
            continue
        # Extract location first (before removing it from title)
        location = _extract_location(item)
        # Extract date
        date_str = _extract_date(item)
        # Extract time
        time_str = _extract_time(item)
        # Clean title: remove date/time/location fragments
        title = _clean_title(item)
        # Skip items that are purely location/date/time specifiers (no real event)
        if not title:
            continue
        todos.append(
            {
                "title": title,
                "date": date_str,
                "time": time_str,
                "location": location,
                "notes": item if item != title else None,
            }
        )
    if not todos:
        todos.append({"title": text.strip()[:100], "date": None, "time": None, "location": None, "notes": None})
    return todos


def _extract_location(text: str) -> str | None:
    for pat in _LOCATION_PATTERNS:
        m = pat.search(text)
        if m:
            loc = m.group(1).strip()
            # Filter out obvious non-location words
            if loc and loc not in ("今天", "明天", "后天"):
                return loc
    return None


def _extract_date(text: str) -> str | None:
    now = datetime.now(timezone.utc)
    for pat, handler in _DATE_PATTERNS:
        m = pat.search(text)
        if m:
            if handler == "_relative_day":
                word = m.group(1)
                if word in ("今天", "今日"):
                    return now.strftime("%Y-%m-%d")
                elif word in ("明天", "明日"):
                    return (now + timedelta(days=1)).strftime("%Y-%m-%d")
                elif word == "后天":
                    return (now + timedelta(days=2)).strftime("%Y-%m-%d")
            elif handler == "_en_relative_day":
                word = m.group(1).lower()
                if word == "today":
                    return now.strftime("%Y-%m-%d")
                elif word == "tomorrow":
                    return (now + timedelta(days=1)).strftime("%Y-%m-%d")
                elif word == "the day after tomorrow":
                    return (now + timedelta(days=2)).strftime("%Y-%m-%d")
            elif handler in ("_next_weekday", "_this_weekday"):
                weekday_char = m.group(1)
                target = _WEEKDAY_MAP.get(weekday_char)
                if target is not None:
                    current = now.weekday()
                    delta = target - current
                    if handler == "_next_weekday" or delta <= 0:
                        delta += 7
                    return (now + timedelta(days=delta)).strftime("%Y-%m-%d")
            elif handler in ("_en_next_weekday", "_en_this_weekday"):
                target = _EN_WEEKDAY_MAP.get(m.group(1).lower()[:3])
                if target is not None:
                    current = now.weekday()
                    delta = target - current
                    if handler == "_en_next_weekday" or delta <= 0:
                        delta += 7
                    return (now + timedelta(days=delta)).strftime("%Y-%m-%d")
            elif handler == "_month_day":
                month = int(m.group(1))
                day = int(m.group(2))
                try:
                    d = now.replace(month=month, day=day)
                    if d < now:
                        d = d.replace(year=now.year + 1)
                    return d.strftime("%Y-%m-%d")
                except ValueError:
                    continue
            elif handler == "_en_month_day":
                month = _EN_MONTH_MAP.get(m.group(1).lower()[:3])
                day = int(m.group(2))
                if month:
                    try:
                        d = now.replace(month=month, day=day)
                        if d < now:
                            d = d.replace(year=now.year + 1)
                        return d.strftime("%Y-%m-%d")
                    except ValueError:
                        continue
            elif handler == "_en_day_month":
                day = int(m.group(1))
                month = _EN_MONTH_MAP.get(m.group(2).lower()[:3])
                if month:
                    try:
                        d = now.replace(month=month, day=day)
                        if d < now:
                            d = d.replace(year=now.year + 1)
                        return d.strftime("%Y-%m-%d")
                    except ValueError:
                        continue
    return None


def _extract_time(text: str) -> str | None:
    for pat, handler in _TIME_PATTERNS:
        m = pat.search(text)
        if m:
            if handler == "_cn_time":
                period = m.group(1)
                hour = int(m.group(2))
                # Check for "半" (half hour) in the original match
                minute = 30 if "半" in m.group(0) else (int(m.group(3)) if m.group(3) else 0)
                if period in ("下午", "晚上") and hour < 12:
                    hour += 12
                elif period == "中午" and hour < 12:
                    hour = 12
                return f"{hour:02d}:{minute:02d}"
            elif handler == "_cn_char_time":
                period = m.group(1)
                hour = _cn_num_to_int(m.group(2))
                if hour is None:
                    continue
                minute = 30 if "半" in m.group(0) else 0
                if period in ("下午", "晚上") and hour < 12:
                    hour += 12
                elif period == "中午" and hour < 12:
                    hour = 12
                return f"{hour:02d}:{minute:02d}"
            elif handler == "_en_ampm_time":
                hour = int(m.group(1))
                minute = int(m.group(2)) if m.group(2) else 0
                ampm = m.group(3).lower()
                if ampm == "pm" and hour < 12:
                    hour += 12
                elif ampm == "am" and hour == 12:
                    hour = 0
                return f"{hour:02d}:{minute:02d}"
            elif handler == "_hmm_time":
                hour = int(m.group(1))
                minute = int(m.group(2))
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return f"{hour:02d}:{minute:02d}"
    return None


def _clean_title(text: str) -> str | None:
    """Remove date/time/location fragments to get a clean event title.

    Returns None if the text contained only date/time/location words
    (no actual event content).
    """
    s = text
    # Remove Chinese date expressions
    s = re.sub(r"(今天|今日|明天|明日|后天)", "", s)
    s = re.sub(r"下?(?:周|星期|礼拜)[一二三四五六日天]", "", s)
    s = re.sub(r"\d{1,2}月\d{1,2}日?", "", s)
    s = re.sub(r"\d{1,2}[-/]\d{1,2}", "", s)
    # Remove English date expressions
    s = re.sub(r"\b(?:the day after tomorrow|tomorrow|today)\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\b(?:next|this)\s+(?:mon|tue|wed|thu|fri|sat|sun)\w*\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2}\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\b", "", s, flags=re.IGNORECASE)
    # Remove Chinese time expressions (Arabic and Chinese numerals)
    s = re.sub(r"(上午|下午|晚上|中午|早上|凌晨|早晨)?\s*\d{1,2}点(?:\d{1,2}分|半)?", "", s)
    s = re.sub(r"(上午|下午|晚上|中午|早上|凌晨|早晨)?\s*[一二两三四五六七八九十]{1,2}点(?:半)?", "", s)
    # Remove English time expressions
    s = re.sub(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", "", s)
    # Remove "全天" (all-day marker)
    s = re.sub(r"全天", "", s)
    # Remove location expressions: 在[地点], 地点[：]X (keep "出差" as it's the event)
    s = re.sub(r"在[\u4e00-\u9fa5A-Za-z0-9_\-]{2,20}?(?=" + _LOCATION_STOP_VERBS + r"|[，。；、\n]|$)", "", s)
    s = re.sub(r"地点[：:]?\s*[\u4e00-\u9fa5A-Za-z0-9_\-]{2,20}", "", s)
    s = re.sub(r"去[\u4e00-\u9fa5A-Za-z0-9_\-]{2,20}$", "", s)
    # Remove English location: in/at [place]
    s = re.sub(r"\b(?:in|at)\s+(?:Room\s+\w+|[A-Z][A-Za-z0-9_\-]*(?:\s+[A-Z][A-Za-z0-9_\-]*)*)", "", s)
    # Clean up
    s = re.sub(r"[，。；、\s]+", " ", s).strip()
    # Remove stray prepositions left after removal
    s = re.sub(r"\b(?:at|in|on|for|to|from)\b", "", s, flags=re.IGNORECASE).strip()
    if not s:
        return None
    return s


def _clean(value) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _combine_datetime(date_str: str | None, time_str: str | None) -> str | None:
    """Combine date and time strings into an ISO 8601 UTC datetime."""
    if not date_str:
        return None
    date_str = date_str.strip()

    date = None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m-%d", "%m/%d"):
        try:
            dt = datetime.strptime(date_str, fmt)
            if fmt in ("%m-%d", "%m/%d"):
                dt = dt.replace(year=datetime.now().year)
            date = dt.date()
            break
        except ValueError:
            continue

    if date is None:
        now = datetime.now(timezone.utc)
        low = date_str.lower()
        if low == "today":
            date = now.date()
        elif low == "tomorrow":
            date = (now + timedelta(days=1)).date()
        else:
            m = re.match(r"\+(\d+)d", low)
            if m:
                date = (now + timedelta(days=int(m.group(1)))).date()

    if date is None:
        return None

    hour, minute = 9, 0
    if time_str:
        time_str = time_str.strip()
        for fmt in ("%H:%M", "%H:%M:%S", "%H时%M分", "%H点"):
            try:
                t = datetime.strptime(time_str, fmt)
                hour, minute = t.hour, t.minute
                break
            except ValueError:
                continue

    dt = datetime.combine(date, datetime.min.time()).replace(
        hour=hour, minute=minute, tzinfo=timezone.utc
    )
    return dt.isoformat()
