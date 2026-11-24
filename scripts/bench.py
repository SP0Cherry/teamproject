#!/usr/bin/env python
"""Benchmark the list-todos endpoint; write reports/bench.md.

Measurement boundary (see reports/bench.md): in-process ASGITransport exercises
the full app + DB path (routing, middleware, query, serialization) against an
isolated file SQLite with a stubbed LLM. TCP/uvicorn overhead is excluded, so
P95 is a conservative lower bound. Deterministic and offline-replayable
(APP_ENV=test, no real model or network) per TEST-05; threshold per OPS-09.

Exit 0 when all requests return 200 AND P95 <= 500ms, else 1.
"""

from __future__ import annotations

import asyncio
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
for p in (str(ROOT), str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Configure BEFORE importing app modules; env overrides .env for these keys.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LLM_BASE_URL", "")
os.environ.setdefault("LLM_API_KEY", "")
os.environ.setdefault("LLM_MODEL", "")

REPORTS = ROOT / "reports"
THRESHOLD_MS = 500.0
SEED_TODOS = 20
CONCURRENCY = 20
TOTAL_REQUESTS = 200
WARMUP = 10


async def _build_app(tmpdir: str):
    from sqlalchemy import create_engine as create_sync_engine
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    import app.models  # noqa: F401  (register tables on Base.metadata)
    from app.db.base import Base
    from app.db.session import get_db
    from app.main import app as fastapi_app

    db_path = str(Path(tmpdir) / "bench.db")
    sync_eng = create_sync_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(sync_eng)
    sync_eng.dispose()

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with SessionLocal() as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    return fastapi_app, SessionLocal, engine


async def _seed(SessionLocal, client) -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"username": "benchuser", "password": "password123"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "benchuser", "password": "password123"},
    )
    token = login.json()["data"]["access_token"]
    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    uid = me.json()["data"]["user_id"]

    from app.models.todo import Todo, TodoStatus

    async with SessionLocal() as db:
        for i in range(SEED_TODOS):
            db.add(Todo(owner_id=uid, title=f"bench todo {i}", status=TodoStatus.PENDING))
        await db.commit()
    return token


async def _one(client, token) -> tuple[float, int]:
    t0 = time.perf_counter()
    r = await client.get(
        "/api/v1/todos", headers={"Authorization": f"Bearer {token}"}
    )
    dt = (time.perf_counter() - t0) * 1000.0
    return dt, r.status_code


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    k = int(round((p / 100.0) * (len(sorted_vals) - 1)))
    return sorted_vals[max(0, min(len(sorted_vals) - 1, k))]


def _write_report(tmpdir_name: str, ok: bool, latencies: list[float],
                  elapsed: float, rps: float) -> bool:
    s = sorted(latencies)
    p50 = _percentile(s, 50)
    p95 = _percentile(s, 95)
    p99 = _percentile(s, 99)
    avg = statistics.mean(latencies) if latencies else 0.0
    passed = ok and p95 <= THRESHOLD_MS

    import datetime as _dt
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    REPORTS.mkdir(exist_ok=True)
    lines = [
        "# 压测报告 bench",
        "",
        f"- 生成时间：{now}",
        f"- 环境：进程内 ASGITransport + 独立文件 SQLite（临时库 `{tmpdir_name}`），"
        "`APP_ENV=test`，LLM 打桩，断网可重放（TEST-05）",
        "- 测量边界：覆盖路由 / 中间件 / DB 查询 / 序列化全链路，不含 TCP 与 uvicorn 调度开销，故 P95 为保守下界",
        "- 目标接口：`GET /api/v1/todos`（列表接口）",
        f"- 数据规模：单用户 {SEED_TODOS} 条待办",
        f"- 脚本参数：并发数={CONCURRENCY}，总请求数={TOTAL_REQUESTS}，预热={WARMUP}",
        "",
        "## 结果",
        "",
        "| 指标 | 值 |",
        "| --- | --- |",
        f"| 请求全部 200 | {'是' if ok else '否'} |",
        f"| P50 (ms) | {p50:.2f} |",
        f"| P95 (ms) | {p95:.2f} |",
        f"| P99 (ms) | {p99:.2f} |",
        f"| 平均 (ms) | {avg:.2f} |",
        f"| 吞吐 (req/s) | {rps:.1f} |",
        f"| 总耗时 (s) | {elapsed:.2f} |",
        "",
        "## 阈值对照",
        "",
        f"- 判据：列表接口正向 P95 ≤ {THRESHOLD_MS:.0f}ms（OPS-09）",
        f"- 实测 P95 = {p95:.2f}ms → **{'通过' if passed else '不通过'}**",
        "",
        "## 复跑命令",
        "",
        "```bash",
        "python scripts/bench.py",
        "```",
        "",
        "> 说明：进程内测量不含网络栈。如需含 TCP 的端到端测量，可在 CI 中以 uvicorn 子进程重跑同一脚本逻辑。",
    ]
    (REPORTS / "bench.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return passed


async def main() -> int:
    from httpx import ASGITransport, AsyncClient

    tmpdir = tempfile.mkdtemp(prefix="bench_")
    tmpdir_name = Path(tmpdir).name
    app, SessionLocal, engine = await _build_app(tmpdir)
    transport = ASGITransport(app=app)
    latencies: list[float] = []
    ok = True
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch(
            "app.services.agent.loop.chat_completion_with_tools",
            new_callable=AsyncMock,
        ) as m:
            m.return_value = {
                "role": "assistant", "content": "{}",
                "tool_calls": None, "time_context": None,
            }
            token = await _seed(SessionLocal, client)
            for _ in range(WARMUP):
                await _one(client, token)
            sem = asyncio.Semaphore(CONCURRENCY)

            async def _bounded():
                async with sem:
                    return await _one(client, token)

            t0 = time.perf_counter()
            results = await asyncio.gather(*[_bounded() for _ in range(TOTAL_REQUESTS)])
            elapsed = time.perf_counter() - t0
            for dt, code in results:
                latencies.append(dt)
                if code != 200:
                    ok = False
    await engine.dispose()
    app.dependency_overrides.clear()

    rps = TOTAL_REQUESTS / elapsed if elapsed > 0 else 0.0
    passed = _write_report(tmpdir_name, ok, latencies, elapsed, rps)
    p95 = _percentile(sorted(latencies), 95)
    print(f"P95={p95:.2f}ms rps={rps:.1f} all_200={ok} passed={passed}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
