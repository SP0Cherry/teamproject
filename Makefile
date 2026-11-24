# Unified quality gate for course delivery (capability: delivery-gate).
#
# Local (Windows): use `mingw32-make` (bundled with Git for Windows). Put the
# backend venv on PATH first, then run:
#   $env:Path = "backend\.venv\Scripts;" + $env:Path; mingw32-make check
# CI (Linux): `make check` / `make check-security` (after installing deps).
#
# Any sub-command returning non-zero stops the gate with a non-zero exit code.

PYTHON ?= python

# Documented dependency-audit exceptions (no patched release exists AND assessed
# not exploitable in this app — see reports/checklist.md 安全核查).
#   PYSEC-2026-4298 (python-jose): only exploitable when algorithms are not
#     explicitly restricted; app pins algorithms=["HS256"] + symmetric secret.
#   PYSEC-2026-1325 (ecdsa, transitive via python-jose): only affects ECDSA
#     signing/keygen; app uses HS256 only and never calls ecdsa.SigningKey.
PIP_AUDIT_IGNORE := --ignore-vuln PYSEC-2026-4298 --ignore-vuln PYSEC-2026-1325

.PHONY: check check-security bench

check:
	cd backend && $(PYTHON) -m pytest -q
	cd backend && $(PYTHON) ../apitest/run_all.py
	cd frontend && npm test

check-security:
	cd backend && $(PYTHON) -m pip_audit -r requirements.txt $(PIP_AUDIT_IGNORE)
	$(PYTHON) scripts/check_secrets.py

bench:
	$(PYTHON) scripts/bench.py
