"""Validate migrations against a temporary PostgreSQL instance (DATA-04)."""

import sys
import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config
from embedded_postgres import PostgresServer


def main():
    with tempfile.TemporaryDirectory() as data_dir:
        pg = PostgresServer(Path(data_dir))
        pg.ensure_pgdata_inited()
        pg.ensure_postgres_running()

        try:
            url = pg.get_uri()
            # Convert to psycopg2 URL for alembic
            url = url.replace("postgresql://", "postgresql+psycopg2://")
            print(f"Test DB URL: {url}")

            alembic_cfg = Config("alembic.ini")
            alembic_cfg.set_main_option("sqlalchemy.url", url)

            # 1. Initial migration
            print("\n=== upgrade head (initial) ===")
            command.upgrade(alembic_cfg, "head")
            print("OK")

            # 2. Idempotency: run again
            print("\n=== upgrade head again (idempotency) ===")
            command.upgrade(alembic_cfg, "head")
            print("OK")

            # 3. Recovery: downgrade then re-upgrade
            print("\n=== downgrade -1 (recovery) ===")
            command.downgrade(alembic_cfg, "-1")
            print("OK")

            print("\n=== upgrade head (recovery) ===")
            command.upgrade(alembic_cfg, "head")
            print("OK")

            print("\n=== ALL MIGRATION CHECKS PASSED ===")
            return 0
        finally:
            pg.cleanup()


if __name__ == "__main__":
    sys.exit(main())
