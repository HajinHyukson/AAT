import type { AttributionChartResponse } from "../lib/types";

const PERIOD_NEAR_ZERO_PCT = 0.000001;
const FALLBACK_START_PRICE_USD = 100;

export const PERIOD_BAR_RANGE_KEY = "bar_draw_range_usd";

export type PeriodBarDirection = "positive" | "negative" | "flat";

export type PeriodBarSegment = {
  driver: string;
  value_pct: number;
  delta_usd: number;
  y0: number;
  y1: number;
};

export type PeriodBarRowValue =
  | string
  | number
  | null
  | [number, number]
  | PeriodBarSegment[];

export type PeriodBarRow = {
  date: string;
  price_change_pct: number;
  close_price_usd: number | null;
  start_price_usd: number | null;
  price_change_usd: number | null;
  bar_bottom_usd: number;
  bar_top_usd: number;
  bar_start_edge_usd: number;
  bar_end_edge_usd: number;
  bar_draw_range_usd: [number, number];
  direction: PeriodBarDirection;
  __segments: PeriodBarSegment[];
  [key: string]: PeriodBarRowValue;
};

export function buildPeriodBarRows(chart: AttributionChartResponse | null): PeriodBarRow[] {
  if (!chart) {
    return [];
  }
  const closeByDate = new Map(
    chart.price_points.map((point) => [dateKey(point.date), finitePositiveNumber(point.adjusted_close)]),
  );
  let previous:
    | { direction: PeriodBarDirection; bottom: number; top: number; close: number | null }
    | null = null;
  return [...chart.attribution_points]
    .sort((left, right) => dateKey(left.date).localeCompare(dateKey(right.date)))
    .map((point) => {
      const contributionByDriver = new Map<string, number>();
      for (const contribution of point.contributions) {
        contributionByDriver.set(
          contribution.driver,
          (contributionByDriver.get(contribution.driver) ?? 0) + contribution.contribution_pct,
        );
      }

      const priceChangePct = finiteNumber(point.observed_return_pct);
      const direction = periodDirection(priceChangePct);
      const closePrice = closeByDate.get(dateKey(point.date)) ?? closeFromFallback(previous, priceChangePct);
      const startPrice = startPriceFromReturn(closePrice, priceChangePct, previous);
      const priceChangeUsd =
        startPrice !== null && closePrice !== null ? closePrice - startPrice : null;
      const anchor = previous ? periodAnchor(previous, direction) : startPrice ?? closePrice ?? FALLBACK_START_PRICE_USD;
      const magnitude = Math.abs(priceChangeUsd ?? anchor * (priceChangePct / 100));
      const barBottom = direction === "negative" ? anchor - magnitude : anchor;
      const barTop = direction === "positive" ? anchor + magnitude : anchor;
      const startEdge = anchor;
      const endEdge =
        direction === "positive" ? barTop : direction === "negative" ? barBottom : anchor;
      const segments = buildPeriodSegments(
        anchor,
        startPrice ?? closePrice ?? anchor,
        contributionByDriver,
        chart.driver_order,
      );
      const drawBottom = Math.min(
        barBottom,
        ...segments.map((segment) => segment.y0),
      );
      const drawTop = Math.max(
        barTop,
        ...segments.map((segment) => segment.y1),
      );

      const row: PeriodBarRow = {
        date: dateKey(point.date),
        price_change_pct: priceChangePct,
        close_price_usd: closePrice,
        start_price_usd: startPrice,
        price_change_usd: priceChangeUsd,
        bar_bottom_usd: barBottom,
        bar_top_usd: barTop,
        bar_start_edge_usd: startEdge,
        bar_end_edge_usd: endEdge,
        bar_draw_range_usd: normalizeRange(drawBottom, drawTop),
        direction,
        __segments: segments,
      };

      for (const [driver, value] of contributionByDriver) {
        row[periodDriverDataKey(driver)] = value;
      }
      previous = { direction, bottom: barBottom, top: barTop, close: closePrice };
      return row;
    });
}

export function buildPeriodYDomain(rows: PeriodBarRow[]): [number, number] {
  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;
  for (const row of rows) {
    min = Math.min(min, row.bar_bottom_usd, row.bar_draw_range_usd[0]);
    max = Math.max(max, row.bar_top_usd, row.bar_draw_range_usd[1]);
  }
  if (!Number.isFinite(min) || !Number.isFinite(max)) {
    return [0, 1];
  }
  const span = max - min;
  const padding = Math.max(span * 0.08, Math.max(Math.abs(max), 1) * 0.002);
  return span <= PERIOD_NEAR_ZERO_PCT ? [min - 1, max + 1] : [min - padding, max + padding];
}

export function periodDriverDataKey(driver: string) {
  return `period_driver_${driver}`;
}

export function periodContributionValue(row: PeriodBarRow, driver: string) {
  const value = row[periodDriverDataKey(driver)];
  return typeof value === "number" ? value : 0;
}

function buildPeriodSegments(
  anchor: number,
  basePrice: number,
  contributionByDriver: Map<string, number>,
  driverOrder: string[],
) {
  const driverOrderSet = new Set(driverOrder);
  const orderedDrivers = [
    ...driverOrder.filter((driver) => contributionByDriver.has(driver)),
    ...Array.from(contributionByDriver.keys()).filter((driver) => !driverOrderSet.has(driver)),
  ];

  let cursor = anchor;
  const segments: PeriodBarSegment[] = [];
  for (const driver of orderedDrivers) {
    const valuePct = contributionByDriver.get(driver) ?? 0;
    const deltaUsd = basePrice * (valuePct / 100);
    const next = cursor + deltaUsd;
    if (Math.abs(deltaUsd) > PERIOD_NEAR_ZERO_PCT) {
      segments.push({
        driver,
        value_pct: valuePct,
        delta_usd: deltaUsd,
        y0: Math.min(cursor, next),
        y1: Math.max(cursor, next),
      });
    }
    cursor = next;
  }
  return segments;
}

function periodAnchor(
  previous: { direction: PeriodBarDirection; bottom: number; top: number } | null,
  direction: PeriodBarDirection,
) {
  if (!previous) {
    return 0;
  }
  if (direction === "negative" && previous.direction === "negative") {
    return previous.bottom;
  }
  return previous.top;
}

function periodDirection(value: number): PeriodBarDirection {
  if (value > PERIOD_NEAR_ZERO_PCT) {
    return "positive";
  }
  if (value < -PERIOD_NEAR_ZERO_PCT) {
    return "negative";
  }
  return "flat";
}

function normalizeRange(bottom: number, top: number): [number, number] {
  if (Math.abs(top - bottom) <= PERIOD_NEAR_ZERO_PCT) {
    return [bottom, bottom + PERIOD_NEAR_ZERO_PCT];
  }
  return [bottom, top];
}

function finiteNumber(value: number) {
  return Number.isFinite(value) ? value : 0;
}

function finitePositiveNumber(value: number) {
  return Number.isFinite(value) && value > 0 ? value : null;
}

function closeFromFallback(
  previous: { close: number | null } | null,
  priceChangePct: number,
) {
  const startPrice = previous?.close ?? FALLBACK_START_PRICE_USD;
  return startPrice * (1 + priceChangePct / 100);
}

function startPriceFromReturn(
  closePrice: number | null,
  priceChangePct: number,
  previous: { close: number | null } | null,
) {
  if (closePrice === null) {
    return previous?.close ?? null;
  }
  const returnRatio = 1 + priceChangePct / 100;
  if (Math.abs(returnRatio) <= PERIOD_NEAR_ZERO_PCT) {
    return previous?.close ?? closePrice;
  }
  const startPrice = closePrice / returnRatio;
  return Number.isFinite(startPrice) && startPrice > 0
    ? startPrice
    : previous?.close ?? closePrice;
}

function dateKey(value: string) {
  return value.slice(0, 10);
}
