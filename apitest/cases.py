"""apitest cases: normal / failure / boundary / end-to-end (TEST-01/03/08/09).

Assertions use concrete business codes and HTTP statuses (TEST-09), not just
"no error". Each case is independent: it registers its own users and cleans up
implicitly via the per-run isolated DB (TEST-04).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class Check:
    name: str
    group: str
    ok: bool
    detail: str
    duration_ms: int = 0


class Recorder:
    def __init__(self, group: str) -> None:
        self.group = group
        self.checks: list[Check] = []

    async def check(self, name: str, cond: bool, detail: str) -> None:
        self.checks.append(
            Check(name=name, group=self.group, ok=bool(cond), detail=detail[:300])
        )


def _uniq(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _register_login(harness, rec: Recorder, username: str = ""):
    client = harness.new_client()
    username = username or _uniq("user")
    password = "Passw0rd!123"
    r = await client.register(username, password)
    await rec.check("注册新用户成功", r.status == 200 and r.ok,
                    f"status={r.status} code={r.code}")
    r = await client.login(username, password)
    await rec.check("登录成功并拿到令牌", r.status == 200 and r.ok
                    and isinstance(r.data, dict) and bool(r.data.get("access_token")),
                    f"status={r.status} code={r.code}")
    me = await client.me()
    user_id = (me.data or {}).get("user_id") if isinstance(me.data, dict) else None
    await rec.check("受保护接口 /auth/me 可访问", me.status == 200 and bool(user_id),
                    f"status={me.status} user_id={'yes' if user_id else 'no'}")
    return client, user_id


# ---------------------------------------------------------------- 正常路径
async def case_normal_flow(harness) -> list[Check]:
    rec = Recorder("正常")
    started = time.monotonic()
    try:
        client, _ = await _register_login(harness, rec)

        r = await client.post("/api/v1/tool-servers", {
            "name": _uniq("good"), "base_url": harness.good_mcp_url, "token": harness.token,
        })
        server_id = (r.data or {}).get("id") if isinstance(r.data, dict) else None
        await rec.check("登记工具服务器（未连接）", r.status == 200 and r.ok
                        and (r.data or {}).get("status") == "unconnected",
                        f"status={r.status} code={r.code} body={r.data}")

        r = await client.post(f"/api/v1/tool-servers/{server_id}/connect")
        tools = (r.data or {}).get("discovered_tools") or []
        tool_names = {t.get("name") for t in tools if isinstance(t, dict)}
        await rec.check("连接并发现工具（status=connected）",
                        r.status == 200 and (r.data or {}).get("status") == "connected"
                        and "unit_convert" in tool_names,
                        f"status={r.status} server_status={(r.data or {}).get('status')} tools={sorted(tool_names)}")

        r = await client.get("/api/v1/tool-servers")
        listed = r.data if isinstance(r.data, list) else []
        await rec.check("列表含已连接服务器且不回传令牌",
                        r.status == 200 and any(s.get("id") == server_id for s in listed)
                        and all("token_cipher" not in s and "token" not in s for s in listed),
                        f"count={len(listed)}")

        r = await client.get(f"/api/v1/tool-servers/{server_id}/tools")
        await rec.check("查询发现的工具清单", r.status == 200
                        and any(t.get("name") == "unit_convert"
                                for t in ((r.data or {}).get("tools") or [])),
                        f"status={r.status}")

        r = await client.post(f"/api/v1/tool-servers/{server_id}/disconnect")
        await rec.check("断开连接（status=unconnected，清空清单）",
                        r.status == 200 and (r.data or {}).get("status") == "unconnected"
                        and not (r.data or {}).get("discovered_tools"),
                        f"status={r.status} server_status={(r.data or {}).get('status')}")
    finally:
        await client.aclose()
    for c in rec.checks:
        c.duration_ms = round((time.monotonic() - started) * 1000)
    return rec.checks


# ---------------------------------------------------------------- 失败路径
async def case_failure_flow(harness) -> list[Check]:
    rec = Recorder("失败")
    started = time.monotonic()
    client_a = client_b = None
    try:
        client_a, _ = await _register_login(harness, rec)
        client_b, _ = await _register_login(harness, rec)

        r = await client_a.post("/api/v1/tool-servers", {
            "name": _uniq("srv"), "base_url": harness.good_mcp_url, "token": harness.token,
        })
        server_id = (r.data or {}).get("id") if isinstance(r.data, dict) else None

        for label, method in [("非所有者 GET 详情", "get"), ("非所有者连接", "connect"),
                              ("非所有者删除", "delete")]:
            if method == "get":
                rb = await client_b.get(f"/api/v1/tool-servers/{server_id}")
            elif method == "connect":
                rb = await client_b.post(f"/api/v1/tool-servers/{server_id}/connect")
            else:
                rb = await client_b.delete(f"/api/v1/tool-servers/{server_id}")
            await rec.check(f"{label}返回 404（与不存在不可区分）",
                            rb.status == 404, f"status={rb.status} code={rb.code}")

        # unreachable base_url -> connect fails with status=error
        r = await client_a.post("/api/v1/tool-servers", {
            "name": _uniq("down"), "base_url": "http://127.0.0.1:9/unreachable", "token": "x",
        })
        down_id = (r.data or {}).get("id") if isinstance(r.data, dict) else None
        r = await client_a.post(f"/api/v1/tool-servers/{down_id}/connect")
        await rec.check("连接不可达服务器 -> status=error 且不阻断",
                        r.status == 200 and (r.data or {}).get("status") == "error"
                        and bool((r.data or {}).get("last_error")),
                        f"server_status={(r.data or {}).get('status')}")

        # wrong token against a live server -> connect status=error
        r = await client_a.post("/api/v1/tool-servers", {
            "name": _uniq("badtok"), "base_url": harness.good_mcp_url, "token": "wrong-token",
        })
        bad_id = (r.data or {}).get("id") if isinstance(r.data, dict) else None
        r = await client_a.post(f"/api/v1/tool-servers/{bad_id}/connect")
        await rec.check("错误令牌连接 -> status=error",
                        r.status == 200 and (r.data or {}).get("status") == "error",
                        f"server_status={(r.data or {}).get('status')}")
    finally:
        for c in (client_a, client_b):
            if c is not None:
                await c.aclose()
    for c in rec.checks:
        c.duration_ms = round((time.monotonic() - started) * 1000)
    return rec.checks


# ---------------------------------------------------------------- 边界
async def case_boundary(harness) -> list[Check]:
    rec = Recorder("边界")
    started = time.monotonic()
    client = None
    try:
        client, _ = await _register_login(harness, rec)

        # name length boundary: 128 allowed, 129 rejected (TEST-03)
        r = await client.post("/api/v1/tool-servers", {
            "name": "a" * 128, "base_url": harness.good_mcp_url, "token": harness.token,
        })
        await rec.check("服务器名长度上限 128 可登记", r.ok,
                        f"status={r.status} code={r.code}")
        r = await client.post("/api/v1/tool-servers", {
            "name": "a" * 129, "base_url": harness.good_mcp_url, "token": harness.token,
        })
        await rec.check("服务器名超过 128 -> PARAM_INVALID 400",
                        r.status == 400 and r.code == "PARAM_INVALID",
                        f"status={r.status} code={r.code}")
        r = await client.post("/api/v1/tool-servers", {
            "name": "", "base_url": harness.good_mcp_url, "token": harness.token,
        })
        await rec.check("服务器名为空 -> PARAM_INVALID 400",
                        r.status == 400 and r.code == "PARAM_INVALID",
                        f"status={r.status} code={r.code}")

        # bad ref format -> 422
        r = await client.post("/api/v1/skills", {
            "name": _uniq("sk"), "capability": "qa", "tool_refs": ["bad format!!"],
        })
        await rec.check("技能引用格式非法 -> BUSINESS_RULE 422",
                        r.status == 422 and r.code == "BUSINESS_RULE",
                        f"status={r.status} code={r.code}")

        # register a server but do NOT connect, then reference it -> 422
        r = await client.post("/api/v1/tool-servers", {
            "name": _uniq("idle"), "base_url": harness.good_mcp_url, "token": harness.token,
        })
        idle_name = (r.data or {}).get("name") if isinstance(r.data, dict) else None
        r = await client.post("/api/v1/skills", {
            "name": _uniq("sk2"), "capability": "qa", "tool_refs": [f"unit_convert@{idle_name}"],
        })
        await rec.check("引用未连接服务器 -> BUSINESS_RULE 422",
                        r.status == 422 and r.code == "BUSINESS_RULE",
                        f"status={r.status} code={r.code}")

        # connect a good server, then reference a tool it doesn't advertise -> 422
        r = await client.post("/api/v1/tool-servers", {
            "name": _uniq("g"), "base_url": harness.good_mcp_url, "token": harness.token,
        })
        gid = (r.data or {}).get("id")
        gname = (r.data or {}).get("name")
        await client.post(f"/api/v1/tool-servers/{gid}/connect")
        r = await client.post("/api/v1/skills", {
            "name": _uniq("sk3"), "capability": "qa", "tool_refs": [f"nope@{gname}"],
        })
        await rec.check("引用不存在的工具 -> BUSINESS_RULE 422",
                        r.status == 422 and r.code == "BUSINESS_RULE",
                        f"status={r.status} code={r.code}")

        # pagination bounds
        r = await client.get("/api/v1/tool-call-records", {"page_size": 101})
        await rec.check("page_size 超过上限 -> PARAM_INVALID 400",
                        r.status == 400 and r.code == "PARAM_INVALID",
                        f"status={r.status} code={r.code}")
        r = await client.get("/api/v1/tool-call-records", {"page_size": 0})
        await rec.check("page_size 小于下限 -> PARAM_INVALID 400",
                        r.status == 400 and r.code == "PARAM_INVALID",
                        f"status={r.status} code={r.code}")
    finally:
        if client is not None:
            await client.aclose()
    for c in rec.checks:
        c.duration_ms = round((time.monotonic() - started) * 1000)
    return rec.checks


# ---------------------------------------------------------------- 端到端
async def case_end_to_end(harness) -> list[Check]:
    rec = Recorder("端到端")
    started = time.monotonic()
    client = None
    try:
        client, user_id = await _register_login(harness, rec)
        if not user_id:
            return rec.checks

        # seed a chunk so QA retrieval enters the tool path
        await harness.seed_chunk(user_id, "关于单位换算 meter foot 的笔记内容")

        # connect good + bad servers
        r = await client.post("/api/v1/tool-servers", {
            "name": "good", "base_url": harness.good_mcp_url, "token": harness.token,
        })
        await client.post(f"/api/v1/tool-servers/{(r.data or {}).get('id')}/connect")
        r = await client.post("/api/v1/tool-servers", {
            "name": "bad", "base_url": harness.bad_mcp_url, "token": harness.token,
        })
        await client.post(f"/api/v1/tool-servers/{(r.data or {}).get('id')}/connect")

        # skills bound to both refs, for both capabilities
        for cap in ("qa", "notification_extraction"):
            r = await client.post("/api/v1/skills", {
                "name": _uniq("skill"), "capability": cap,
                "tool_refs": ["unit_convert@good", "boom@bad"],
            })
            await rec.check(f"保存 {cap} 技能（双引用）成功",
                            r.status == 200 and r.ok,
                            f"status={r.status} code={r.code}")

        def _meta_statuses(stream):
            for fr in stream.frames:
                if fr.event == "meta" and isinstance(fr.data, dict):
                    return [(c.get("tool"), c.get("status"))
                            for c in fr.data.get("tool_calls", []) if isinstance(c, dict)]
            return []

        # QA success
        s = await client.sse("/api/v1/qa/ask", {"question": "TRIGGER_SUCCESS 10米等于多少英尺"})
        st = _meta_statuses(s)
        await rec.check("QA SSE：success 调用在 meta 可见",
                        s.status == 200 and any(t == "unit_convert@good" and x == "success" for t, x in st),
                        f"http={s.status} meta={st}")
        await rec.check("QA SSE：有 data 正文且 done 收尾",
                        any(f.event == "data" for f in s.frames) and any(f.event == "done" for f in s.frames),
                        f"events={[f.event for f in s.frames]}")

        # QA rejected
        s = await client.sse("/api/v1/qa/ask", {"question": "TRIGGER_REJECTED 测试一下"})
        st = _meta_statuses(s)
        await rec.check("QA SSE：rejected 调用在 meta 可见",
                        any(t == "unit_convert@good" and x == "rejected" for t, x in st),
                        f"http={s.status} meta={st}")

        # QA error
        s = await client.sse("/api/v1/qa/ask", {"question": "TRIGGER_ERROR 测试一下"})
        st = _meta_statuses(s)
        await rec.check("QA SSE：error 调用在 meta 可见",
                        any(t == "boom@bad" and x == "error" for t, x in st),
                        f"http={s.status} meta={st}")

        # notification parse success
        s = await client.sse("/api/v1/notifications/parse",
                             {"text": "TRIGGER_SUCCESS 明天下午三点开会，请准时参加"})
        st = _meta_statuses(s)
        has_data = any(f.event == "data" and isinstance(f.data, dict)
                       and f.data.get("title") for f in s.frames)
        await rec.check("通知解析 SSE：工具调用与解析正文均输出",
                        s.status == 200 and any(x == "success" for _, x in st) and has_data,
                        f"http={s.status} meta={st} events={[f.event for f in s.frames]}")

        # records API must surface all three statuses
        r = await client.get("/api/v1/tool-call-records", {"page_size": 100})
        items = (r.data or {}).get("items") if isinstance(r.data, dict) else []
        results = {it.get("result") for it in items if isinstance(it, dict)}
        await rec.check("记录列表：success/rejected/error 三种状态均可见",
                        {"success", "rejected", "error"}.issubset(results),
                        f"results={sorted(results)} count={len(items)}")

        # raw DB read confirms persistence (TEST-08: assert side effect, not just response)
        raw = await harness.list_records_raw(user_id)
        raw_results = {r["result"] for r in raw}
        await rec.check("数据库持久化：三种状态均已落库",
                        {"success", "rejected", "error"}.issubset(raw_results),
                        f"raw_results={sorted(raw_results)} count={len(raw)}")

        # owner isolation: a different user sees zero records
        other, other_id = await _register_login(harness, rec)
        try:
            ro = await other.get("/api/v1/tool-call-records")
            other_items = (ro.data or {}).get("items") if isinstance(ro.data, dict) else []
            await rec.check("记录按 owner 隔离：其他用户查不到",
                            ro.status == 200 and len(other_items) == 0,
                            f"other_count={len(other_items)}")
        finally:
            await other.aclose()
    finally:
        if client is not None:
            await client.aclose()
    for c in rec.checks:
        c.duration_ms = round((time.monotonic() - started) * 1000)
    return rec.checks


ALL_CASES = [
    ("正常路径：登记/连接/列出/断开", case_normal_flow),
    ("失败路径：越权 404 / 不可达 / 错误令牌", case_failure_flow),
    ("边界：冲突 / 技能校验 / 分页", case_boundary),
    ("端到端：连接→技能→提问/解析→三种记录状态", case_end_to_end),
]
