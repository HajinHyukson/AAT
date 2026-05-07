from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from urllib.parse import quote

from sqlalchemy import create_engine, text

from jobs.pilot_sp500_common import PILOT_DATABASE_NAME, pilot_database_url, safe_database_identifier


@dataclass
class PilotDbInitReport:
    database_name: str
    database_url: str
    created: bool
    migrated: bool

    def render(self) -> str:
        return (
            "pilot DB initialized "
            f"database={self.database_name} created={self.created} migrated={self.migrated}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create and migrate the local S&P 500 pilot database")
    parser.add_argument("--database-name", default=PILOT_DATABASE_NAME)
    parser.add_argument("--skip-create", action="store_true")
    parser.add_argument("--skip-alembic", action="store_true")
    args = parser.parse_args()

    report = init_pilot_sp500_db(
        database_name=args.database_name,
        skip_create=args.skip_create,
        skip_alembic=args.skip_alembic,
    )
    print(report.render())
    print(f"DATABASE_URL={report.database_url}")


def init_pilot_sp500_db(
    *,
    database_name: str = PILOT_DATABASE_NAME,
    skip_create: bool = False,
    skip_alembic: bool = False,
) -> PilotDbInitReport:
    safe_database_identifier(database_name)
    created = False
    if not skip_create:
        created = create_database_if_missing(database_name=database_name)
    database_url = pilot_database_url(database_name=database_name)
    if not skip_alembic:
        run_alembic_upgrade(database_url=database_url)
    return PilotDbInitReport(
        database_name=database_name,
        database_url=database_url,
        created=created,
        migrated=not skip_alembic,
    )


def create_database_if_missing(*, database_name: str) -> bool:
    admin_url = postgres_admin_url()
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :database_name"),
                {"database_name": database_name},
            ).scalar_one_or_none()
            if exists:
                return False
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
            return True
    finally:
        engine.dispose()


def postgres_admin_url() -> str:
    user = os.getenv("POSTGRES_USER", "attribution")
    password = quote(os.getenv("POSTGRES_PASSWORD", "attribution"), safe="")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_HOST_PORT", "55432")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/postgres"


def run_alembic_upgrade(*, database_url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=env)


if __name__ == "__main__":
    main()
