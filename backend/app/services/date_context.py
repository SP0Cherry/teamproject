"""Trusted request clock and deterministic calendar semantics (AI-01, PROD-13)."""
import re
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.config import settings


def capture_time(now=None, timezone_name=None):
    zone = timezone_name or settings.timezone
    instant = now if now is not None else datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError('clock must provide an aware datetime')
    local = instant.astimezone(ZoneInfo(zone))
    return {'request_sent_at': local.isoformat(timespec='seconds'),
            'current_date': local.date().isoformat(), 'current_time': local.strftime('%H:%M:%S'),
            'current_weekday': local.isoweekday(), 'weekday_label': '星期' + '一二三四五六日'[local.weekday()], 'timezone': zone}


def date_basis(text, context):
    matches = re.findall(r'(?:发布于|发布日期[：:]?|通知日期[：:]?)\s*(\d{4}[-/]\d{2}[-/]\d{2})', text)
    try:
        dates = {date.fromisoformat(s.replace('/', '-')).isoformat() for s in matches}
    except ValueError:
        return None
    if len(dates) > 1 or (not dates and not context.get('current_date')):
        return None
    return {'date': next(iter(dates)) if dates else context['current_date'],
            'timezone': context['timezone'], 'source': 'source_text' if dates else 'request_time',
            'source_text': matches[0] if matches else None}


def resolve_date(expression, basis):
    if not expression:
        return None
    if not isinstance(expression, str):
        raise ValueError('date expression must be text')
    value = expression.strip()
    full = re.search(r'(?<!\d)(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})日?', value)
    if full:
        return date(*map(int, full.groups())).isoformat()
    if not basis or not basis.get('date'):
        return None
    base = date.fromisoformat(basis['date'])
    relative = {'今天': 0, '今日': 0, 'today': 0, '明天': 1, '明日': 1,
                'tomorrow': 1, '后天': 2, 'the day after tomorrow': 2}
    for word in sorted(relative, key=len, reverse=True):
        if word in value.lower():
            return (base + timedelta(days=relative[word])).isoformat()
    plus = re.fullmatch(r'\+(\d+)d', value)
    if plus:
        return (base + timedelta(days=int(plus[1]))).isoformat()
    match = re.search(r'(下|本|这)?(?:周|星期|礼拜)([一二三四五六日天])', value)
    if match:
        weekday = '一二三四五六日'.index(match[2].replace('天', '日'))
        return (base - timedelta(days=base.weekday()) + timedelta(days=weekday + (7 if match[1] == '下' else 0))).isoformat()
    match = re.search(r'\b(this|next)\s+(mon|tue|wed|thu|fri|sat|sun)\w*', value.lower())
    if match:
        weekday = ['mon','tue','wed','thu','fri','sat','sun'].index(match[2])
        return (base - timedelta(days=base.weekday()) + timedelta(days=weekday + (7 if match[1] == 'next' else 0))).isoformat()
    match = re.search(r'(?<!\d)(\d{1,2})[月/-](\d{1,2})日?', value)
    if match:
        return date(base.year, int(match[1]), int(match[2])).isoformat()
    months = ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec']
    match = re.search(r'\b(' + '|'.join(months) + r')\w*\s+(\d{1,2})\b', value.lower())
    if match:
        return date(base.year, months.index(match[1])+1, int(match[2])).isoformat()
    return None


def validate_candidate(item, index=1):
    """Validate the whole batch before adding any ORM objects."""
    from app.core.response import ApiError
    try:
        if not isinstance(item, dict):
            raise ValueError('candidate must be an object')
        allowed = {'title','text','description','notes','location','date','time','due_at','deadline',
                   'due_date','due_precision','due_timezone','accept_no_deadline','date_basis',
                   'date_expression','source_text','warnings','needs_confirmation'}
        if set(item) - allowed:
            raise ValueError('unexpected candidate fields')
        zone = item.get('due_timezone') or settings.timezone
        ZoneInfo(zone)
        title = item.get('title') or item.get('text')
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 255:
            raise ValueError('标题必填且不能超过255字')
        explicit = item.get('due_at') or item.get('deadline')
        instant = datetime.fromisoformat(explicit) if explicit else None
        if instant and instant.tzinfo is None:
            raise ValueError('精确时刻必须包含时区偏移')
        if item.get('due_at') and item.get('deadline') and datetime.fromisoformat(item['due_at']) != datetime.fromisoformat(item['deadline']):
            raise ValueError('截止时间字段冲突')
        if 'date' in item or 'time' in item:
            fields = time_fields(item.get('date'), item.get('time'), zone)
            local_instant = datetime.fromisoformat(fields['due_at']) if fields['due_at'] else None
            if instant and instant != local_instant:
                raise ValueError('当地时间与UTC时刻冲突')
            instant = local_instant
            day = date.fromisoformat(fields['due_date']) if fields['due_date'] else None
            if item.get('due_date') and (day is None or date.fromisoformat(item['due_date']) != day):
                raise ValueError('日期字段冲突')
        else:
            day = date.fromisoformat(item['due_date']) if item.get('due_date') else None
        if instant and day:
            raise ValueError('仅日期与精确时刻不能同时存在')
        precision = 'datetime' if instant else 'date' if day else 'unknown'
        if item.get('due_precision') and item['due_precision'] != precision:
            raise ValueError('时间精度与时间字段不一致')
        if item.get('time') and not item.get('date') and item.get('accept_no_deadline') is not True:
            raise ValueError('请补充日期或明确接受无截止时间')
        notes = item.get('notes') or item.get('description')
        if item.get('time') and not item.get('date'):
            notes = (notes or '') + '\n原文时间：' + item['time'] + '（已确认无截止日期）'
        return {'title': title.strip(), 'description': notes, 'location': item.get('location'),
                'due_at': instant.astimezone(timezone.utc) if instant else None,
                'due_date': day, 'due_precision': precision, 'due_timezone': zone}
    except (ValueError, TypeError, KeyError):
        raise ApiError(code='PARAM_INVALID', message=f'第{index}项标题或时间无效，请检查日期、时区及时间精度', data={'item': index, 'field': 'time'}) from None


def serialize_todo(todo):
    due = todo.due_at
    if due and due.tzinfo is None:  # SQLite fixtures return naive timestamps; storage is UTC.
        due = due.replace(tzinfo=timezone.utc)
    return {'id': todo.id, 'title': todo.title, 'description': todo.description,
            'location': todo.location, 'due_at': due.isoformat() if due else None,
            'due_date': todo.due_date.isoformat() if todo.due_date else None,
            'due_precision': todo.due_precision, 'due_timezone': todo.due_timezone,
            'status': todo.status.value}


def time_fields(date_value, time_value, timezone_name=None):
    zone = timezone_name or settings.timezone
    ZoneInfo(zone)
    day = date.fromisoformat(date_value) if date_value else None
    clock = time.fromisoformat(time_value) if time_value else None
    if clock and clock.tzinfo is not None:
        raise ValueError('local time must not contain an offset')
    due = datetime.combine(day, clock, ZoneInfo(zone)).astimezone(timezone.utc) if day and clock else None
    return {'date': day.isoformat() if day else None, 'time': clock.strftime('%H:%M') if clock else None,
            'due_at': due.isoformat() if due else None,
            'due_date': day.isoformat() if day and not clock else None,
            'due_precision': 'datetime' if due else 'date' if day else 'unknown', 'due_timezone': zone}


def normalize_candidate(item, text, context):
    basis = date_basis(text, context)
    expression = item.get('date_expression') or item.get('date')
    source = item.get('source_text')
    warnings = []
    if source and isinstance(source, str) and source in text:
        relative = re.search(r'(?:下|本|这)?(?:周|星期|礼拜)[一二三四五六日天]|后天|明天|明日|今天|今日|\b(?:this|next)\s+(?:mon|tue|wed|thu|fri|sat|sun)\w*|\btomorrow\b|\btoday\b', source, re.I)
        if relative:
            expression = relative[0]  # Never trust a model-computed absolute date for a relative expression.
    if source and source not in text:
        warnings.append('来源片段不在原文中，请确认时间')
        expression = None
    if item.get('date_expression') and (not isinstance(item['date_expression'], str) or item['date_expression'] not in text):
        warnings.append('日期表达不在原文中，请确认日期')
        expression = None
    try:
        resolved = resolve_date(expression, basis)
        fields = time_fields(resolved, item.get('time'), context['timezone'])
        if resolved and resolve_date(expression, None) == resolved:
            basis = None  # A full calendar date does not depend on a publication or request day.
    except (ValueError, TypeError):
        fields = time_fields(None, None, context['timezone'])
        warnings.append('日期或时间无效，请按原文修正')
    if expression and not fields['date']:
        warnings.append('日期基准缺失或冲突，请确认日期')
    return {**fields, 'date_expression': expression, 'date_basis': basis,
            'source_text': source, 'warnings': warnings,
            'needs_confirmation': bool(warnings or (expression and basis and basis['source'] == 'request_time') or (fields['time'] and not fields['date']))}
