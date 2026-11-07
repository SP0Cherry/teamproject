"""E2E auth flow test through the real FastAPI app on a real PostgreSQL."""

import asyncio
import sys
import tempfile
from pathlib import Path

import httpx
from alembic import command
from alembic.config import Config
from embedded_postgres import PostgresServer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import get_db
from app.main import app


async def main():
    with tempfile.TemporaryDirectory() as data_dir:
        pg = PostgresServer(Path(data_dir))
        pg.ensure_pgdata_inited()
        pg.ensure_postgres_running()

        try:
            url = pg.get_uri().replace("postgresql://", "postgresql+psycopg2://")
            alembic_cfg = Config("alembic.ini")
            alembic_cfg.set_main_option("sqlalchemy.url", url)
            command.upgrade(alembic_cfg, "head")

            async_url = url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
            test_engine = create_async_engine(async_url)
            TestSession = async_sessionmaker(
                test_engine, class_=AsyncSession, expire_on_commit=False
            )

            async def override_get_db():
                async with TestSession() as session:
                    yield session

            app.dependency_overrides[get_db] = override_get_db

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                print("=== Register ===")
                r = await client.post(
                    "/api/v1/auth/register",
                    json={"username": "e2euser", "password": "password123"},
                )
                print(f"  status={r.status_code}, code={r.json()['code']}")
                assert r.status_code == 200

                print("=== Login ===")
                r = await client.post(
                    "/api/v1/auth/login",
                    json={"username": "e2euser", "password": "password123"},
                )
                print(f"  status={r.status_code}, code={r.json()['code']}")
                assert r.status_code == 200
                token = r.json()["data"]["access_token"]
                print(f"  access_token present: {bool(token)}")

                print("=== Access protected /me ===")
                r = await client.get(
                    "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
                )
                print(
                    f"  status={r.status_code}, code={r.json()['code']}, "
                    f"username={r.json()['data']['username']}"
                )
                assert r.status_code == 200

                print("=== Wrong credentials ===")
                r = await client.post(
                    "/api/v1/auth/login",
                    json={"username": "e2euser", "password": "wrongpass"},
                )
                print(f"  status={r.status_code}, code={r.json()['code']}")
                assert r.status_code == 401

            print("\n=== ALL E2E CHECKS PASSED ===")
            return 0
        finally:
            pg.cleanup()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
