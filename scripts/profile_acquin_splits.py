"""Read-only check: is Acquin price history corporate-action adjusted?

Large negative one-day returns across many names indicate unadjusted splits.
Also inspects Kakao (035720) around its 2021-04-15 5:1 split.
"""

from __future__ import annotations

from pathlib import Path

import psycopg

from profile_acquin_db import load_db_url


def main() -> None:
    url = load_db_url(Path(__file__).resolve().parent.parent / ".env")
    with psycopg.connect(url, connect_timeout=20) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            print("== days with return_1d <= -0.4 (split suspects) ==")
            cur.execute(
                """
                select ticker, date, return_1d, close
                from fact_price_daily
                where return_1d <= -0.4
                order by return_1d
                limit 20
                """
            )
            for row in cur.fetchall():
                print("  " + " | ".join(str(v) for v in row))
            cur.execute(
                "select count(*) from fact_price_daily where return_1d <= -0.4"
            )
            print(f"  total such rows: {cur.fetchone()[0]}")
            print()

            print("== Kakao 035720 around 2021-04-15 split ==")
            cur.execute(
                """
                select date, close, adj_close, volume, return_1d
                from fact_price_daily
                where ticker = '035720'
                  and date between '2021-04-09' and '2021-04-20'
                order by date
                """
            )
            for row in cur.fetchall():
                print("  " + " | ".join(str(v) for v in row))


if __name__ == "__main__":
    main()
