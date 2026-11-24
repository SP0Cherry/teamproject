#!/usr/bin/env python
"""Scan git-tracked files for hardcoded secrets; exit 1 on any hit.

Part of ``make check-security``. Zero external dependencies, offline-runnable.
Excludes gitignored files (``.env`` is never tracked), tests/stubs/apitest, and
known placeholder values so defaults like ``change_me`` don't false-positive.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Path substrings that are allowed to contain fake/test secrets.
_EXCLUDE_PARTS = (
    "tests/", "/test", "conftest", "stub_", "apitest/", "__pycache__",
    ".venv", "node_modules", "openspec/", "reports/", "docs/", "scripts/check_secrets.py",
)
# Extensions that are documentation / data / lock files — not scanned for secrets.
_EXCLUDE_EXTS = {
    ".md", ".txt", ".csv", ".json", ".lock", ".cfg", ".ini", ".toml",
    ".yml", ".yaml", ".gitignore", ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ".ico", ".pdf", ".zip", ".tar", ".gz", ".woff", ".woff2", ".ttf", ".eot",
}

# Patterns. ASSIGN captures the secret value in group 2.
_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
_ASSIGN = re.compile(
    r"(?i)(secret|api[_-]?key|token|password|passwd|access[_-]?key|"
    r"auth[_-]?token|client[_-]?secret)\s*[:=]\s*[\"']([^\"']{6,})[\"']"
)
_PREFIX = re.compile(
    r"(ghp_[A-Za-z0-9]{30,}|xox[baprs]-[A-Za-z0-9-]{10,}|"
    r"AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,}|sk_live_[A-Za-z0-9]{20,})"
)
# Values that look like placeholders / defaults / templates — not real secrets.
_PLACEHOLDER = re.compile(
    r"(?i)^(change[_\-]?me.*|xxx+|not[_\-]?a[_\-]?secret.*|test|testing|"
    r"stub|example|demo|placeholder|dummy|fake|your[_-].*|password123|"
    r"123456|none|null|true|false|0|1)$"
)


def _tracked_files() -> list[str]:
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files"],
            capture_output=True, text=True, check=True,
        )
        return [line for line in out.stdout.splitlines() if line]
    except (subprocess.CalledProcessError, FileNotFoundError):
        # git unavailable: walk tracked-ish source as a degraded fallback,
        # skipping obvious non-source dirs. Never silently pass.
        files: list[str] = []
        skip = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache"}
        for p in ROOT.rglob("*"):
            if any(part in skip for part in p.relative_to(ROOT).parts):
                continue
            if p.is_file():
                files.append(str(p.relative_to(ROOT)).replace("\\", "/"))
        return files


def _should_scan(rel: str) -> bool:
    if any(part in rel for part in _EXCLUDE_PARTS):
        return False
    if Path(rel).suffix.lower() in _EXCLUDE_EXTS:
        return False
    return True


def _is_placeholder(value: str) -> bool:
    v = value.strip()
    if len(v) < 8:
        return True
    if _PLACEHOLDER.match(v):
        return True
    if "$" in v or "{" in v or "%" in v:
        return True
    if len(set(v)) == 1:
        return True
    return False


def main() -> int:
    hits: list[str] = []
    for rel in _tracked_files():
        if not _should_scan(rel):
            continue
        path = ROOT / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if _PRIVATE_KEY.search(line):
                hits.append(f"{rel}:{i}: private key block")
                continue
            m = _ASSIGN.search(line)
            if m and not _is_placeholder(m.group(2)):
                hits.append(f"{rel}:{i}: possible secret assignment ({m.group(1)})")
                continue
            if _PREFIX.search(line):
                hits.append(f"{rel}:{i}: prefixed token")
    if hits:
        print("Secrets scan FAILED — hardcoded secret(s) found:")
        for h in hits:
            print(f"  {h}")
        print("Resolve or register an accepted exception before merging.")
        return 1
    print("OK: no hardcoded secrets found in tracked source files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
