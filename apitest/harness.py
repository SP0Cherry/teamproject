"""apitest harness: isolated SQLite DB, in-process backend, helper servers.

Design (TEST-04/05/06):
- Backend runs in-process via ASGITransport with ``get_db`` overridden to an
  isolated file-based SQLite DB (schema created from models, mirroring the
  project's pytest convention). pgvector cosine ordering falls back to unordered
  owner-filtered results on SQLite, which is sufficient to exercise the tool path.
- LLM is a local stub (no real model calls). The real ``mcp-server`` artifact and
  a faulty MCP stub run as subprocesses on free localhost ports so the host's
  HTTP discovery + call path is exercised end-to-end.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
MCP_SERVER_DIR = ROOT / "mcp-server"
TEST_TOKEN = "apitest-mcp-token-not-a-secret"

for p in (str(ROOT), str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Configure the backend BEFORE importing app modules (env overrides .env).
os.environ["LLM_BASE_URL"] = ""  # set after stub port known
os.environ["LLM_API_KEY"] = "apitest-stub-key"
os.environ["LLM_MODEL"] = "apitest-stub-model"
os.environ["MCP_SERVER_TOKEN_ENCRYPT_KEY"] = "apitest-encrypt-key-change-me-32b"
os.environ["APP_ENV"] = "test"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_http(url: str, timeout: float = 20.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


class Harness:
    def __init__(self) -> None:
        self._tmpdir = tempfile.mkdtemp(prefix="apitest_")
        self._procs: list[subprocess.Popen] = []
        self.engine = None
        self.SessionLocal = None
        self.good_mcp_url = ""
        self.bad_mcp_url = ""
        self.llm_url = ""
        self.token = TEST_TOKEN
        self._app = None

    # ---- setup ----
    def start(self) -> "Harness":
        # helper servers first so we know the LLM port before importing app
        good_port = free_port()
        bad_port = free_port()
        llm_port = free_port()
        self.good_mcp_url = f"http://127.0.0.1:{good_port}"
        self.bad_mcp_url = f"http://127.0.0.1:{bad_port}"
        self.llm_url = f"http://127.0.0.1:{llm_port}"

        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")

        # real mcp-server (cwd = mcp-server, module app.main:app)
        mcp_env = dict(env)
        mcp_env["MCP_AUTH_TOKEN"] = self.token
        self._spawn(
            [sys.executable, "-m", "uvicorn", "app.main:app",
             "--host", "127.0.0.1", "--port", str(good_port), "--log-level", "warning"],
            cwd=str(MCP_SERVER_DIR), env=mcp_env,
        )
        # faulty mcp stub
        bad_env = dict(env)
        bad_env["MCP_AUTH_TOKEN"] = self.token
        self._spawn(
            [sys.executable, "-m", "uvicorn", "apitest.stub_mcp_bad:app",
             "--host", "127.0.0.1", "--port", str(bad_port), "--log-level", "warning"],
            cwd=str(ROOT), env=bad_env,
        )
        # stub LLM
        self._spawn(
            [sys.executable, "-m", "uvicorn", "apitest.stub_llm:app",
             "--host", "127.0.0.1", "--port", str(llm_port), "--log-level", "warning"],
            cwd=str(ROOT), env=env,
        )

        for url in (f"{self.good_mcp_url}/health",
                    f"{self.bad_mcp_url}/health",
                    f"{self.llm_url}/health"):
            if not _wait_http(url):
                self.close()
                raise RuntimeError(f"helper server did not become healthy: {url}")

        # Now point backend config at the stub LLM and import the app.
        os.environ["LLM_BASE_URL"] = self.llm_url
        self._init_app()
        return self

    def _spawn(self, cmd: list[str], cwd: str, env: dict) -> None:
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        proc = subprocess.Popen(
            cmd, cwd=cwd, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        self._procs.append(proc)

    def _init_app(self) -> None:
        from sqlalchemy import create_engine as create_sync_engine
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from sqlalchemy.pool import StaticPool

        import app.models  # noqa: F401  (register tables on Base.metadata)
        from app.db.base import Base
        from app.db.session import get_db
        from app.main import app as fastapi_app

        self._app = fastapi_app
        db_path = str(Path(self._tmpdir) / "apitest.db")
        # Create schema with a sync engine (no event loop needed).
        sync_eng = create_sync_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(sync_eng)
        sync_eng.dispose()

        self.engine = create_async_engine(
            f"sqlite+aiosqlite:///{db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

        async def override_get_db():
            async with self.SessionLocal() as session:
                yield session

        fastapi_app.dependency_overrides[get_db] = override_get_db

    @staticmethod
    async def _create_all(engine, Base):  # kept for reference; unused now
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @property
    def app(self):
        return self._app

    def new_client(self):
        from apitest.client import ApiClient
        return ApiClient(self._app)

    async def seed_chunk(self, user_id: str, text: str) -> None:
        """Insert an attachment + one owned chunk so QA retrieval hits the tool path."""
        import uuid
        from app.models.attachment import Attachment, AttachmentStatus
        from app.repositories.resource_chunk import ResourceChunkRepository
        from app.services.indexer import _demo_embedding

        async with self.SessionLocal() as db:
            att = Attachment(
                id=str(uuid.uuid4()), owner_id=user_id, filename="note.txt",
                title="note", mime_type="text/plain", file_size=len(text),
                storage_path=f"/tmp/{uuid.uuid4()}", status=AttachmentStatus.SUCCEEDED,
                extracted_text=text, version=1,
            )
            db.add(att)
            await db.flush()
            await ResourceChunkRepository(db).create(
                attachment_id=att.id, version=1, chunk_index=0,
                content=text, embedding=_demo_embedding(text),
                owner_id=user_id, group_id=None,
            )
            await db.commit()

    async def list_records_raw(self, user_id: str) -> list[dict]:
        """Read persisted records directly (bypassing API) for assertions."""
        from sqlalchemy import select
        from app.models.tool_call_record import ToolCallRecord

        async with self.SessionLocal() as db:
            res = await db.execute(
                select(ToolCallRecord).where(ToolCallRecord.owner_id == user_id)
            )
            return [
                {"tool_name": r.tool_name, "server_name": r.server_name,
                 "result": r.result.value, "round_index": r.round_index}
                for r in res.scalars().all()
            ]

    async def aclose(self) -> None:
        for proc in self._procs:
            try:
                proc.terminate()
            except Exception:
                pass
        for proc in self._procs:
            try:
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        self._procs.clear()
        if self.engine is not None:
            await self.engine.dispose()
        if self._app is not None:
            self._app.dependency_overrides.clear()
        try:
            import shutil
            shutil.rmtree(self._tmpdir, ignore_errors=True)
        except Exception:
            pass
