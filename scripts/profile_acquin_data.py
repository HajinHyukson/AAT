"""Read-only data profiling of the Acquin Railway Postgres (phase 2).

Answers the adapter-design questions: adjusted prices, ingestion-time
fidelity, coverage, universe composition, and enum values.
"""

from __future__ import annotations

from pathlib import Path

import psycopg

from profile_acquin_db import load_db_url


QUERIES: list[tuple[str, str]] = [
    (
        "price coverage",
        """
        select min(date), max(date), count(*) as rows,
               count(distinct ticker) as tickers
        from fact_price_daily
        """,
    ),
    (
        "adjusted vs raw close",
        """
        select count(*) as rows,
               count(adj_close) as adj_close_present,
               sum(case when adj_close is distinct from close then 1 else 0 end)
                 as adj_differs_from_close,
               count(market_cap) as market_cap_present,
               count(shares_outstanding) as shares_present,
               count(return_1d) as return_present
        from fact_price_daily
        """,
    ),
    (
        "price source / freshness values",
        """
        select source, freshness_state, count(*)
        from fact_price_daily
        group by source, freshness_state
        order by count(*) desc
        """,
    ),
    (
        "created_at distribution (ingestion-time fidelity, prices)",
        """
        select created_at::date as ingest_day, count(*),
               min(date) as min_trade_date, max(date) as max_trade_date
        from fact_price_daily
        group by created_at::date
        order by ingest_day
        limit 30
        """,
    ),
    (
        "dim_stock composition",
        """
        select market, is_preferred, is_active, count(*),
               count(isin) as isin_present,
               count(delisting_date) as delisted,
               count(sector) as sector_present
        from dim_stock
        group by market, is_preferred, is_active
        order by count(*) desc
        """,
    ),
    (
        "ticker format sample",
        """
        select ticker, isin, name_en, market, sector, listing_date, is_preferred
        from dim_stock
        order by ticker
        limit 8
        """,
    ),
    (
        "index data",
        """
        select index_code, name, min(date), max(date), count(*)
        from fact_index_daily
        group by index_code, name
        """,
    ),
    (
        "investor flow groups",
        """
        select investor_group, count(*), count(distinct ticker) as tickers,
               min(date), max(date)
        from fact_investor_flow_daily
        group by investor_group
        order by investor_group
        """,
    ),
    (
        "foreign holding coverage",
        """
        select count(*) as rows,
               count(foreign_ownership_pct) as ownership_present,
               count(foreign_limit_exhaustion_pct) as limit_present,
               min(date), max(date), count(distinct ticker) as tickers
        from fact_foreign_holding_daily
        """,
    ),
    (
        "per-ticker price row distribution",
        """
        select min(cnt), percentile_cont(0.5) within group (order by cnt),
               max(cnt)
        from (select ticker, count(*) as cnt from fact_price_daily group by ticker) t
        """,
    ),
    (
        "samsung sample rows (005930, last 3 days)",
        """
        select date, open, close, adj_close, volume, trading_value,
               market_cap, return_1d, source, freshness_state, created_at
        from fact_price_daily
        where ticker = '005930'
        order by date desc
        limit 3
        """,
    ),
    (
        "data freshness (max dates per table)",
        """
        select 'price' as t, max(date) from fact_price_daily
        union all select 'flow', max(date) from fact_investor_flow_daily
        union all select 'foreign', max(date) from fact_foreign_holding_daily
        union all select 'index', max(date) from fact_index_daily
        union all select 'features', max(date) from fact_features_daily
        """,
    ),
]


def main() -> None:
    url = load_db_url(Path(__file__).resolve().parent.parent / ".env")
    with psycopg.connect(url, connect_timeout=20) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            for title, sql in QUERIES:
                print(f"== {title} ==")
                try:
                    cur.execute(sql)
                    for row in cur.fetchall():
                        print("  " + " | ".join(str(v) for v in row))
                except Exception as exc:  # noqa: BLE001
                    conn.rollback()
                    print(f"  ERROR: {exc}")
                print()


if __name__ == "__main__":
    main()
