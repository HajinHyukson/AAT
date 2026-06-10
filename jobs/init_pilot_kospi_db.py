from __future__ import annotations

import argparse
from dataclasses import dataclass

from jobs.init_pilot_sp500_db import create_database_if_missing, run_alembic_upgrade
from jobs.pilot_kospi_common import PILOT_KOSPI_DATABASE_NAME, pilot_kospi_database_url
from jobs.pilot_sp500_common import safe_database_identifier


@dataclass
class PilotKospiDbInitReport:
    database_name: str
    database_url: str
    created: bool
    migrated: bool

    def render(self) -> str:
        return (
            "KOSPI pilot DB initialized "
            f"database={self.database_name} created={self.created} migrated={self.migrated}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create and migrate the local KOSPI pilot database")
    parser.add_argument("--database-name", default=PILOT_KOSPI_DATABASE_NAME)
    parser.add_argument("--skip-create", action="store_true")
    parser.add_argument("--skip-alembic", action="store_true")
    args = parser.parse_args()

    report = init_pilot_kospi_db(
        database_name=args.database_name,
        skip_create=args.skip_create,
        skip_alembic=args.skip_alembic,
    )
    print(report.render())
    print(f"DATABASE_URL={report.database_url}")


def init_pilot_kospi_db(
    *,
    database_name: str = PILOT_KOSPI_DATABASE_NAME,
    skip_create: bool = False,
    skip_alembic: bool = False,
) -> PilotKospiDbInitReport:
    safe_database_identifier(database_name)
    created = False
    if not skip_create:
        created = create_database_if_missing(database_name=database_name)
    database_url = pilot_kospi_database_url(database_name=database_name)
    if not skip_alembic:
        run_alembic_upgrade(database_url=database_url)
    return PilotKospiDbInitReport(
        database_name=database_name,
        database_url=database_url,
        created=created,
        migrated=not skip_alembic,
    )


if __name__ == "__main__":
    main()
