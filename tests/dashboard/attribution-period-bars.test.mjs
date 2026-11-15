import assert from "node:assert/strict";
import { test } from "node:test";

import {
  buildPeriodBarRows,
  buildPeriodYDomain,
} from "../../dashboard/components/attribution-period-bars.ts";

test("floating period bars anchor each sign transition to the requested prior edge", () => {
  const rows = buildPeriodBarRows(
    chart([
      { date: "2026-01-02", move: 3, close: 103, contributions: { market: 3 } },
      { date: "2026-01-03", move: 2, close: 105.06, contributions: { market: 2 } },
      { date: "2026-01-04", move: -4, close: 100.8576, contributions: { market: -4 } },
      { date: "2026-01-05", move: -2, close: 98.840448, contributions: { market: -2 } },
      { date: "2026-01-06", move: 3, close: 101.80566144, contributions: { market: 3 } },
    ]),
  );

  assertRowEdges(rows[0], { bottom: 100, top: 103, start: 100, end: 103 });
  assertRowEdges(rows[1], { bottom: 103, top: 105.06, start: 103, end: 105.06 });
  assertRowEdges(rows[2], { bottom: 100.8576, top: 105.06, start: 105.06, end: 100.8576 });
  assertRowEdges(rows[3], { bottom: 98.840448, top: 100.8576, start: 100.8576, end: 98.840448 });
  assertRowEdges(rows[4], { bottom: 100.8576, top: 103.82281344, start: 100.8576, end: 103.82281344 });
  assert.equal(rows[4].close_price_usd, 101.80566144);
});

test("floating period y domain includes observed bodies and raw contribution extents", () => {
  const rows = buildPeriodBarRows(
    chart([
      { date: "2026-01-02", move: 1, close: 101, contributions: { market: 4 } },
      { date: "2026-01-03", move: -1, close: 99.99, contributions: { market: -5 } },
    ]),
  );

  const domain = buildPeriodYDomain(rows);

  assert.ok(domain[0] < 95.95, `expected lower domain below raw segment extent, got ${domain[0]}`);
  assert.ok(domain[1] > 104, `expected upper domain above raw segment extent, got ${domain[1]}`);
});

function assertRowEdges(row, expected) {
  assertApprox(row.bar_bottom_usd, expected.bottom);
  assertApprox(row.bar_top_usd, expected.top);
  assertApprox(row.bar_start_edge_usd, expected.start);
  assertApprox(row.bar_end_edge_usd, expected.end);
}

function assertApprox(actual, expected) {
  assert.ok(Math.abs(actual - expected) < 0.000001, `expected ${actual} to equal ${expected}`);
}

function chart(points) {
  return {
    ticker: "AAPL",
    range: "1m",
    cadence: "daily",
    start: points[0]?.date ?? "2026-01-01",
    end: points.at(-1)?.date ?? "2026-01-01",
    price_points: points.map((point) => ({
      date: `${point.date}T00:00:00Z`,
      adjusted_close: point.close,
      cumulative_return_pct: 0,
    })),
    driver_order: ["market", "sector", "peer", "unexplained_residual"],
    attribution_points: points.map((point) => ({
      date: `${point.date}T00:00:00Z`,
      window_start: `${point.date}T00:00:00Z`,
      window_end: `${point.date}T00:00:00Z`,
      observed_return_pct: point.move,
      contributions: Object.entries(point.contributions).map(([driver, value]) => ({
        driver,
        name: driver,
        contribution_pct: value,
        share_of_move: null,
      })),
    })),
  };
}
