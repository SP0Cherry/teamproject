"""Validate migrations against a temporary PostgreSQL instance (DATA-04)."""

import sys
import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config

try:  # Optional local verification dependency; absent in CI install set.
    from embedded_postgres import PostgresServer
except ImportError:
    PostgresServer = None

from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError


def main():
    if PostgresServer is None:
        raise RuntimeError(
            "embedded-postgres is required for migration checks: "
            "pip install embedded-postgres==18.6.3"
        )
    with tempfile.TemporaryDirectory() as data_dir:
        pg = PostgresServer(Path(data_dir))
        pg.ensure_pgdata_inited()
        pg.ensure_postgres_running()

        try:
            url = pg.get_uri()
            # Convert to psycopg2 URL for alembic
            url = url.replace("postgresql://", "postgresql+psycopg2://")
            print("Using an isolated temporary PostgreSQL instance")

            alembic_cfg = Config("alembic.ini")
            alembic_cfg.set_main_option("sqlalchemy.url", url)

            # Seed the previous schema to verify a real expand migration.
            command.upgrade(alembic_cfg, '0014_todo_location')
            engine = create_engine(url)
            with engine.begin() as connection:
                connection.execute(text("INSERT INTO todos(id,owner_id,title,due_at) VALUES('legacy','test','legacy','2026-11-11T07:00:00Z')"))
                connection.execute(text("INSERT INTO todos(id,owner_id,title) VALUES('unknown','test','unknown')"))
                before = connection.execute(text("SELECT due_at FROM todos WHERE id='legacy'")).scalar()

            # 1. Initial migration
            print("\n=== upgrade head (initial) ===")
            command.upgrade(alembic_cfg, "head")
            print("OK")
            with engine.begin() as connection:
                row = connection.execute(text("SELECT due_at,due_precision FROM todos WHERE id='legacy'")).one()
                assert row[0] == before and row[1] == 'datetime'
                assert connection.execute(text("SELECT due_precision FROM todos WHERE id='unknown'")).scalar() == 'unknown'
                connection.execute(text("INSERT INTO todos(id,owner_id,title,due_at) VALUES('old-client','test','old client','2026-11-11T07:00:00Z')"))
                assert connection.execute(text("SELECT due_precision FROM todos WHERE id='old-client'")).scalar() == 'datetime'
            try:
                with engine.begin() as connection:
                    connection.execute(text("INSERT INTO todos(id,owner_id,title,due_at,due_precision) VALUES('invalid','test','invalid','2026-11-11T07:00:00Z','unknown')"))
            except IntegrityError:
                pass
            else:
                raise AssertionError('Inconsistent precision must be rejected')
            print('Legacy timestamps preserved, old writer compatible, constraints enforced')

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

            with engine.begin() as connection:
                connection.execute(text("INSERT INTO todos(id,owner_id,title,due_date,due_precision) VALUES('date-only','test','date only','2026-11-11','date')"))
            try:
                command.downgrade(alembic_cfg, '-1')
            except RuntimeError as error:
                assert 'Export' in str(error)
            else:
                raise AssertionError('Downgrade must refuse to discard date-only data')
            with engine.connect() as connection:
                assert str(connection.execute(text("SELECT due_date FROM todos WHERE id='date-only'")).scalar()) == '2026-11-11'
            engine.dispose()
            print('Date-only data protected against destructive structural downgrade')


            print("\n=== ALL MIGRATION CHECKS PASSED ===")
            return 0
        finally:
            pg.cleanup()


if __name__ == "__main__":
    sys.exit(main())
