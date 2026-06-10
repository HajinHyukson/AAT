"""Read-only profiling of the Acquin Railway Postgres for KOSPI adapter design.

Loads ACQUIN_DB_URL from .env, never prints credentials. Runs introspection
and data-profiling SELECTs only.
"""

from __future__ import annotations

import sys
from pathlib import Path

import psycopg


def load_db_url(env_path: Path) -> str:
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "ACQUIN_DB_URL":
            url = value.strip().strip('"').strip("'")
            if url.startswith("postgresql+psycopg://"):
                url = "postgresql://" + url[len("postgresql+psycopg://"):]
            return url
    raise SystemExit("ACQUIN_DB_URL not found in .env")


def main() -> None:
    url = load_db_url(Path(__file__).resolve().parent.parent / ".env")
    with psycopg.connect(url, connect_timeout=20) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute("select current_database(), version()")
            db, ver = cur.fetchone()
            print(f"connected: db={db}")
            print(f"server: {ver.split(',')[0]}")
            print()

            cur.execute(
                """
                select table_schema, table_name
                from information_schema.tables
                where table_type = 'BASE TABLE'
                  and table_schema not in ('pg_catalog', 'information_schema')
                order by table_schema, table_name
                """
            )
            tables = cur.fetchall()
            print(f"== tables ({len(tables)}) ==")
            for schema, name in tables:
                cur.execute(
                    "select reltuples::bigint from pg_class c "
                    "join pg_namespace n on n.oid = c.relnamespace "
                    "where n.nspname = %s and c.relname = %s",
                    (schema, name),
                )
                row = cur.fetchone()
                est = row[0] if row else -1
                print(f"  {schema}.{name}  (~{est:,} rows)")
            print()

            for schema, name in tables:
                cur.execute(
                    """
                    select column_name, data_type, is_nullable
                    from information_schema.columns
                    where table_schema = %s and table_name = %s
                    order by ordinal_position
                    """,
                    (schema, name),
                )
                cols = cur.fetchall()
                print(f"== {schema}.{name} ==")
                for col, dtype, nullable in cols:
                    print(f"  {col}: {dtype}{'' if nullable == 'YES' else ' NOT NULL'}")
                print()


if __name__ == "__main__":
    main()
