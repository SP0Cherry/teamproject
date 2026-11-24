"""apitest runner: execute all cases, write an HTML report, exit non-zero on failure.

Usage (from repo root, with backend venv):
    backend\\.venv\\Scripts\\python.exe apitest\\run_all.py
    backend\\.venv\\Scripts\\python.exe apitest\\run_all.py --case 端到端

One command reproduces results + report (TEST-06); any failure blocks with a
non-zero exit code (TEST-07). No real AI or network dependencies are contacted
(TEST-05): the LLM and a faulty MCP server are local stubs; the real mcp-server
artifact runs as a subprocess on localhost.
"""

from __future__ import annotations

import argparse
import asyncio
import html
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
for p in (str(ROOT), str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

from apitest.cases import ALL_CASES, Check  # noqa: E402
from apitest.harness import Harness  # noqa: E402


def _build_html(results: list[tuple[str, list[Check]]], elapsed_s: float, out_path: Path) -> None:
    total = sum(len(cs) for _, cs in results)
    failed = [c for _, cs in results for c in cs if not c.ok]
    passed = total - len(failed)
    status_color = "#1a7f37" if not failed else "#cf222e"
    status_text = "ALL PASSED" if not failed else f"{len(failed)} FAILED"

    rows = []
    for case_name, checks in results:
        rows.append(
            f'<tr class="case"><td colspan="5"><strong>{html.escape(case_name)}</strong></td></tr>'
        )
        for c in checks:
            badge = '<span class="ok">PASS</span>' if c.ok else '<span class="no">FAIL</span>'
            rows.append(
                f"<tr><td>{badge}</td><td>{html.escape(c.group)}</td>"
                f"<td>{html.escape(c.name)}</td>"
                f"<td>{c.duration_ms}</td>"
                f"<td>{html.escape(c.detail)}</td></tr>"
            )

    doc = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>apitest report</title>
<style>
 body{{font-family:system-ui,Segoe UI,Arial,sans-serif;margin:24px;color:#1f2328}}
 h1{{margin-bottom:4px}} .sub{{color:#57606a;margin-bottom:16px}}
 .summary{{display:flex;gap:24px;margin:12px 0 20px}}
 .card{{border:1px solid #d0d7de;border-radius:8px;padding:10px 16px}}
 .big{{font-size:26px;font-weight:700;color:{status_color}}}
 table{{border-collapse:collapse;width:100%;font-size:13px}}
 th,td{{border:1px solid #d0d7de;padding:6px 8px;text-align:left;vertical-align:top}}
 th{{background:#f6f8fa}} tr.case td{{background:#f6f8fa}}
 .ok{{color:#1a7f37;font-weight:700}} .no{{color:#cf222e;font-weight:700}}
</style></head><body>
<h1>apitest 报告</h1>
<div class="sub">mcp-http-tool-platform 端到端 · 生成于 {time.strftime('%Y-%m-%d %H:%M:%S')} · 耗时 {elapsed_s:.1f}s</div>
<div class="summary">
 <div class="card"><div class="big">{status_text}</div><div>结论</div></div>
 <div class="card"><div class="big">{passed}</div><div>通过</div></div>
 <div class="card"><div class="big">{len(failed)}</div><div>失败</div></div>
 <div class="card"><div class="big">{total}</div><div>总检查项</div></div>
</div>
<table>
 <thead><tr><th>结果</th><th>分组</th><th>检查项</th><th>耗时(ms)</th><th>详情</th></tr></thead>
 <tbody>{''.join(rows)}</tbody>
</table>
</body></html>"""
    out_path.write_text(doc, encoding="utf-8")


async def run(filter_case: str | None) -> int:
    harness = Harness()
    results: list[tuple[str, list[Check]]] = []
    started = time.monotonic()
    try:
        try:
            harness.start()
        except Exception as exc:
            traceback.print_exc()
            print(f"[FATAL] harness failed to start: {exc}", file=sys.stderr)
            return 2

        for case_name, fn in ALL_CASES:
            if filter_case and filter_case not in case_name:
                continue
            print(f"\n=== {case_name} ===")
            try:
                checks = await fn(harness)
            except Exception:
                traceback.print_exc()
                checks = [Check(name=case_name, group="端到端", ok=False,
                                detail="case raised exception; see console traceback")]
            results.append((case_name, checks))
            for c in checks:
                mark = "PASS" if c.ok else "FAIL"
                print(f"  [{mark}] {c.name} — {c.detail}")

        elapsed = time.monotonic() - started
        out = ROOT / "apitest" / "report.html"
        _build_html(results, elapsed, out)

        total = sum(len(cs) for _, cs in results)
        failed = [c for _, cs in results for c in cs if not c.ok]
        print(f"\n=== 总计 {total} 项，通过 {total - len(failed)}，失败 {len(failed)} ===")
        print(f"报告: {out}")
        return 1 if failed else 0
    finally:
        await harness.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description="apitest runner")
    parser.add_argument("--case", default=None, help="只运行名称包含该子串的用例")
    args = parser.parse_args()
    sys.exit(asyncio.run(run(args.case)))


if __name__ == "__main__":
    main()
