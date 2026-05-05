"use client";

import { useMemo, useRef, useState } from "react";
import type { MouseEvent as ReactMouseEvent } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import { getAttributionChart } from "@/lib/api";
import type {
  AttributionChartPoint,
  AttributionChartRange,
  AttributionChartResponse,
} from "@/lib/types";

const RANGES: { label: string; value: AttributionChartRange }[] = [
  { label: "10D", value: "10d" },
  { label: "1M", value: "1m" },
  { label: "3M", value: "3m" },
  { label: "6M", value: "6m" },
  { label: "1Y", value: "1y" },
  { label: "Max", value: "max" },
];

const DISPLAY_MODES: { label: string; value: DisplayMode }[] = [
  { label: "bp", value: "bps" },
  { label: "USD", value: "usd" },
];

const DRIVER_COLORS: Record<string, string> = {
  market: "#1f4b43",
  sector: "#2f7a62",
  industry: "#3a8a7e",
  peer: "#c8893e",
  style: "#8b6d3f",
  macro: "#44758f",
  positioning: "#d4a84b",
  event: "#7a2e2e",
  unexplained_residual: "#a33b42",
};

const FALLBACK_DRIVER_COLOR = "#57636f";
const THEME = {
  ink: "#23312f",
  primary: "#173f3a",
  secondary: "#c8893e",
  base: "#fffdf8",
  baseSoft: "#f5f0e7",
  line: "#e3d9c9",
  muted: "#6b6256",
  grid: "rgba(93, 74, 42, 0.16)",
};
const CHART_HEIGHT = 360;
const CHART_MARGIN = { top: 16, right: 18, bottom: 8, left: 4 };
const X_AXIS_HEIGHT = 32;
const Y_AXIS_WIDTH = 48;
const POPUP_GUTTER = 8;
const POPUP_OFFSET = 14;
const POPUP_MAX_WIDTH = 288;
const POPUP_MIN_WIDTH = 220;
const POPUP_MAX_HEIGHT = 300;
const NEAR_ZERO_PCT = 0.000001;

type DisplayMode = "bps" | "usd";

type DriverBand = {
  driver: string;
  y0: number;
  y1: number;
};

type ChartRowValue = string | number | null | [number, number] | DriverBand[];

type ChartRow = {
  date: string;
  label: string;
  adjusted_close: number | null;
  cumulative_return_pct: number | null;
  opposite_border_pct: number | null;
  price_change_usd: number | null;
  __bands: DriverBand[];
  [key: string]: ChartRowValue;
};

type HoverState = {
  date: string;
  mouseX: number;
  mouseY: number;
  activeDriver: string | null;
};

type ChartBounds = {
  width: number;
  height: number;
};

export function AttributionChart({
  ticker,
  initialChart,
}: {
  ticker: string;
  initialChart: AttributionChartResponse | null;
}) {
  const [chart, setChart] = useState<AttributionChartResponse | null>(initialChart);
  const [range, setRange] = useState<AttributionChartRange>(initialChart?.range ?? "1m");
  const [displayMode, setDisplayMode] = useState<DisplayMode>("bps");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [dragStart, setDragStart] = useState<string | null>(null);
  const [dragEnd, setDragEnd] = useState<string | null>(null);
  const [selection, setSelection] = useState<{ start: string; end: string } | null>(null);
  const [hover, setHover] = useState<HoverState | null>(null);
  const [chartBounds, setChartBounds] = useState<ChartBounds>({
    width: 0,
    height: CHART_HEIGHT,
  });
  const chartFrameRef = useRef<HTMLDivElement | null>(null);

  const chartRows = useMemo(() => buildChartRows(chart), [chart]);
  const rowByDate = useMemo(
    () => new Map(chartRows.map((row) => [row.date, row])),
    [chartRows],
  );
  const yDomain = useMemo(() => buildYDomain(chartRows), [chartRows]);
  const driverOrder = chart?.driver_order ?? [];
  const selectionSummary = useMemo(
    () => (chart && selection ? buildSelectionSummary(chart, selection.start, selection.end) : null),
    [chart, selection],
  );

  async function selectRange(nextRange: AttributionChartRange) {
    setRange(nextRange);
    setLoading(true);
    setStatus("");
    setSelection(null);
    setHover(null);
    try {
      setChart(await getAttributionChart(ticker, nextRange));
    } catch {
      setStatus("Chart data could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  function readLocalPointer(event: ReactMouseEvent<SVGGraphicsElement>) {
    const frame = chartFrameRef.current;
    if (!frame) {
      return null;
    }
    const rect = frame.getBoundingClientRect();
    const nextBounds = {
      width: rect.width,
      height: rect.height || CHART_HEIGHT,
    };
    setChartBounds((current) =>
      Math.abs(current.width - nextBounds.width) > 0.5 ||
      Math.abs(current.height - nextBounds.height) > 0.5
        ? nextBounds
        : current,
    );
    return {
      mouseX: clamp(event.clientX - rect.left, 0, nextBounds.width),
      mouseY: clamp(event.clientY - rect.top, 0, nextBounds.height),
    };
  }

  function updateHoverForDate(date: string | null, event: ReactMouseEvent<SVGGraphicsElement>) {
    if (!date) {
      setHover(null);
      return;
    }
    const position = readLocalPointer(event);
    const row = rowByDate.get(date) ?? null;
    if (!position || !row) {
      setHover(null);
      return;
    }
    setHover({
      date,
      mouseX: position.mouseX,
      mouseY: position.mouseY,
      activeDriver: findActiveDriver(row, position.mouseY, yDomain, chartBounds.height),
    });
  }

  return (
    <section className="overflow-hidden rounded-[1.4rem] border border-[rgba(93,74,42,0.12)] bg-[#fffdf8]/85 shadow-[0_20px_60px_rgba(18,38,34,0.10)] backdrop-blur-[18px]">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[rgba(93,74,42,0.12)] bg-[linear-gradient(180deg,rgba(255,253,248,0.96),rgba(245,240,231,0.88))] px-5 py-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="h-5 w-1 rounded-full bg-[linear-gradient(180deg,#173f3a,#c8893e)]" />
            <h3 className="text-base font-semibold text-[#173f3a]">Price Attribution Chart</h3>
          </div>
          <p className="mt-1 text-sm text-[#6b6256]">
            {ticker} cumulative move and modeled drivers.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-full border border-[rgba(23,63,58,0.10)] bg-white/60 p-1 text-xs font-semibold shadow-[0_6px_16px_rgba(18,38,34,0.06)]">
            {DISPLAY_MODES.map((item) => (
              <button
                key={item.value}
                type="button"
                className={`h-7 rounded-full px-3 ${
                  displayMode === item.value
                    ? "bg-[#173f3a] text-[#fffdf8]"
                    : "text-[#6b6256] hover:bg-[#f5f0e7]"
                }`}
                onClick={() => setDisplayMode(item.value)}
              >
                {item.label}
              </button>
            ))}
          </div>
          <div className="inline-flex rounded-full border border-[rgba(23,63,58,0.10)] bg-white/60 p-1 text-sm shadow-[0_6px_16px_rgba(18,38,34,0.06)]">
            {RANGES.map((item) => (
              <button
                key={item.value}
                type="button"
                className={`h-7 rounded-full px-3 font-semibold ${
                  range === item.value
                    ? "bg-[#173f3a] text-[#fffdf8]"
                    : "text-[#6b6256] hover:bg-[#f5f0e7]"
                }`}
                onClick={() => selectRange(item.value)}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="px-5 py-4">
        {chartRows.length ? (
          <div
            ref={chartFrameRef}
            className="relative h-[360px] min-h-[360px] w-full min-w-0 rounded-[1.1rem] border border-[rgba(93,74,42,0.10)] bg-[linear-gradient(180deg,rgba(255,253,248,0.82),rgba(245,240,231,0.56))] px-1 py-2"
          >
            <ResponsiveContainer width="100%" height={CHART_HEIGHT} minWidth={1} minHeight={1}>
              <ComposedChart
                data={chartRows}
                margin={CHART_MARGIN}
                onMouseDown={(state, event) => {
                  const date = typeof state.activeLabel === "string" ? state.activeLabel : null;
                  updateHoverForDate(date, event);
                  if (date) {
                    setDragStart(date);
                    setDragEnd(date);
                  }
                }}
                onMouseMove={(state, event) => {
                  const date = typeof state.activeLabel === "string" ? state.activeLabel : null;
                  updateHoverForDate(date, event);
                  if (dragStart && date) {
                    setDragEnd(date);
                  }
                }}
                onMouseLeave={() => {
                  setHover(null);
                  setDragStart(null);
                  setDragEnd(null);
                }}
                onMouseUp={() => {
                  if (dragStart && dragEnd && dragStart !== dragEnd) {
                    setSelection(orderSelection(dragStart, dragEnd));
                  }
                  setDragStart(null);
                  setDragEnd(null);
                }}
              >
                <CartesianGrid stroke={THEME.grid} strokeDasharray="3 4" vertical={false} />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatDateTick}
                  minTickGap={28}
                  height={X_AXIS_HEIGHT}
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: THEME.muted, fontSize: 12 }}
                />
                <YAxis
                  domain={yDomain}
                  tickFormatter={(value) => `${Number(value).toFixed(0)}%`}
                  width={Y_AXIS_WIDTH}
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: THEME.muted, fontSize: 12 }}
                />
                {driverOrder.map((driver) => (
                  <Area
                    key={`positive-band-${driver}`}
                    type="linear"
                    dataKey={driverDataKey(driver, "positive")}
                    fill={driverColor(driver)}
                    fillOpacity={0.5}
                    stroke="none"
                    name={`${driver.replaceAll("_", " ")} positive`}
                    dot={false}
                    isRange
                  />
                ))}
                {driverOrder.map((driver) => (
                  <Area
                    key={`negative-band-${driver}`}
                    type="linear"
                    dataKey={driverDataKey(driver, "negative")}
                    fill={driverColor(driver)}
                    fillOpacity={0.5}
                    stroke="none"
                    name={`${driver.replaceAll("_", " ")} negative`}
                    dot={false}
                    isRange
                  />
                ))}
                {selection ? (
                  <ReferenceArea
                    x1={selection.start}
                    x2={selection.end}
                    fill={THEME.primary}
                    fillOpacity={0.08}
                    strokeOpacity={0}
                  />
                ) : null}
                {dragStart && dragEnd ? (
                  <ReferenceArea
                    x1={dragStart}
                    x2={dragEnd}
                    fill={THEME.primary}
                    fillOpacity={0.12}
                    strokeOpacity={0}
                  />
                ) : null}
                <Line
                  type="linear"
                  dataKey="opposite_border_pct"
                  name="opposite contribution border"
                  stroke={THEME.primary}
                  strokeDasharray="4 5"
                  strokeOpacity={0.75}
                  strokeWidth={2}
                  dot={false}
                />
                <ReferenceLine y={0} stroke="rgba(35,49,47,0.82)" strokeWidth={2} />
                <Line
                  type="monotone"
                  dataKey="cumulative_return_pct"
                  name="price change"
                  stroke={THEME.primary}
                  strokeWidth={4}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  dot={false}
                  connectNulls
                />
              </ComposedChart>
            </ResponsiveContainer>
            {hover ? (
              <ChartHoverBox
                row={rowByDate.get(hover.date) ?? null}
                driverOrder={driverOrder}
                displayMode={displayMode}
                hover={hover}
                bounds={chartBounds}
              />
            ) : null}
          </div>
        ) : (
          <div className="rounded-[1.1rem] border border-[rgba(93,74,42,0.12)] bg-[#f5f0e7]/70 px-4 py-8 text-sm text-[#6b6256]">
            No price history is available for this chart range.
          </div>
        )}

        <div className="mt-3 flex flex-wrap items-start justify-between gap-3 border-t border-[rgba(93,74,42,0.12)] pt-3 text-sm">
          <div className="text-[#6b6256]">
            {loading ? "Loading chart data..." : status || `${chart?.cadence ?? "daily"} attribution cadence`}
          </div>
          {selectionSummary ? (
            <div className="max-w-[520px] text-right">
              <div className="font-semibold">
                {formatDateTick(selectionSummary.start)} to {formatDateTick(selectionSummary.end)}:{" "}
                <span className={selectionSummary.priceChangePct < 0 ? "text-[#a33b42]" : "text-[#2f7a62]"}>
                  {selectionSummary.priceChangePct.toFixed(2)}%
                </span>
              </div>
              {selectionSummary.attributeShares.length ? (
                <div className="mt-1 text-xs text-[#6b6256]">
                  {selectionSummary.attributeShares
                    .map((item) => `${item.name}: ${(item.averageShare * 100).toFixed(1)}%`)
                    .join(" | ")}
                </div>
              ) : (
                <div className="mt-1 text-xs text-[#6b6256]">
                  No attribution rows in this range.
                </div>
              )}
            </div>
          ) : (
            <div className="text-xs text-[#6b6256]">Drag across the chart to summarize a period.</div>
          )}
        </div>
        {driverOrder.length ? (
          <div className="mt-3 flex flex-wrap gap-2 text-xs text-[#6b6256]">
            {driverOrder.map((driver) => (
              <span
                key={driver}
                className="inline-flex items-center gap-1.5 rounded-full border border-[rgba(23,63,58,0.10)] bg-white/55 px-2.5 py-1"
              >
                <span
                  className="inline-block h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: driverColor(driver) }}
                />
                {driver.replaceAll("_", " ")}
              </span>
            ))}
          </div>
        ) : null}
      </div>
    </section>
  );
}

function buildChartRows(chart: AttributionChartResponse | null): ChartRow[] {
  if (!chart) {
    return [];
  }
  const rowsByDate = new Map<string, ChartRow>();
  for (const point of chart.price_points) {
    const date = dateKey(point.date);
    rowsByDate.set(date, {
      date,
      label: date,
      adjusted_close: point.adjusted_close,
      cumulative_return_pct: point.cumulative_return_pct,
      opposite_border_pct: null,
      price_change_usd: null,
      __bands: [],
    });
  }
  const cumulativeByDriver = new Map<string, number>();
  const attributionByDate = new Map<string, Map<string, number>>();
  for (const point of chart.attribution_points) {
    const date = dateKey(point.date);
    const periodByDriver = attributionByDate.get(date) ?? new Map<string, number>();
    for (const contribution of point.contributions) {
      periodByDriver.set(
        contribution.driver,
        (periodByDriver.get(contribution.driver) ?? 0) + contribution.contribution_pct,
      );
    }
    attributionByDate.set(date, periodByDriver);
  }
  const rows = Array.from(rowsByDate.values()).sort((left, right) => left.date.localeCompare(right.date));
  const firstClose = rows.find((row) => typeof row.adjusted_close === "number")?.adjusted_close ?? null;

  for (const row of rows) {
    const periodByDriver = attributionByDate.get(row.date);
    if (periodByDriver) {
      for (const [driver, value] of periodByDriver) {
        cumulativeByDriver.set(driver, (cumulativeByDriver.get(driver) ?? 0) + value);
      }
    }
    row.price_change_usd =
      typeof row.adjusted_close === "number" && typeof firstClose === "number"
        ? row.adjusted_close - firstClose
        : null;
    applyDriverBands(row, chart.driver_order, cumulativeByDriver);
  }
  return rows;
}

function applyDriverBands(
  row: ChartRow,
  driverOrder: string[],
  cumulativeByDriver: Map<string, number>,
) {
  row.__bands = [];
  const priceMove = typeof row.cumulative_return_pct === "number" ? row.cumulative_return_pct : 0;
  const driverValues = driverOrder.map((driver) => ({
    driver,
    value: cumulativeByDriver.get(driver) ?? 0,
  }));

  let positiveCursor = 0;
  let negativeCursor = 0;
  for (const { driver, value } of driverValues) {
    const startsPositive = positiveCursor;
    const startsNegative = negativeCursor;

    row[driverDataKey(driver, "net")] = value;

    if (value > NEAR_ZERO_PCT) {
      positiveCursor += value;
      setBand(row, driver, "positive", startsPositive, positiveCursor, true);
      row[driverDataKey(driver, "negative")] = [startsNegative, startsNegative];
    } else if (value < -NEAR_ZERO_PCT) {
      negativeCursor += value;
      row[driverDataKey(driver, "positive")] = [startsPositive, startsPositive];
      setBand(row, driver, "negative", startsNegative, negativeCursor, true);
    } else {
      row[driverDataKey(driver, "positive")] = [startsPositive, startsPositive];
      row[driverDataKey(driver, "negative")] = [startsNegative, startsNegative];
    }
  }
  const oppositeBorder = priceMove >= 0 ? negativeCursor : positiveCursor;
  row.opposite_border_pct = Math.abs(oppositeBorder) > NEAR_ZERO_PCT ? oppositeBorder : null;
}

function setBand(
  row: ChartRow,
  driver: string,
  side: "positive" | "negative",
  start: number,
  end: number,
  includeHitBand = false,
) {
  const y0 = Math.min(start, end);
  const y1 = Math.max(start, end);
  row[driverDataKey(driver, side)] = [y0, y1];
  if (includeHitBand) {
    row.__bands.push({ driver, y0, y1 });
  }
}

function buildYDomain(rows: ChartRow[]): [number, number] {
  let min = 0;
  let max = 0;
  for (const row of rows) {
    if (typeof row.cumulative_return_pct === "number") {
      min = Math.min(min, row.cumulative_return_pct);
      max = Math.max(max, row.cumulative_return_pct);
    }
    if (typeof row.opposite_border_pct === "number") {
      min = Math.min(min, row.opposite_border_pct);
      max = Math.max(max, row.opposite_border_pct);
    }
    for (const band of row.__bands) {
      min = Math.min(min, band.y0, band.y1);
      max = Math.max(max, band.y0, band.y1);
    }
  }
  const span = max - min;
  const padding = Math.max(span * 0.08, 0.25);
  return span <= NEAR_ZERO_PCT ? [-1, 1] : [min - padding, max + padding];
}

function findActiveDriver(
  row: ChartRow,
  mouseY: number,
  yDomain: [number, number],
  chartHeight: number,
) {
  const yValue = yValueFromMouse(mouseY, yDomain, chartHeight);
  if (yValue === null) {
    return null;
  }
  const tolerance = Math.max((yDomain[1] - yDomain[0]) * 0.012, 0.03);
  const hit = row.__bands.find(
    (band) => yValue >= band.y0 - tolerance && yValue <= band.y1 + tolerance,
  );
  return hit?.driver ?? null;
}

function yValueFromMouse(mouseY: number, yDomain: [number, number], chartHeight: number) {
  const plotTop = CHART_MARGIN.top;
  const plotBottom = Math.max(plotTop + 1, chartHeight - CHART_MARGIN.bottom - X_AXIS_HEIGHT);
  const clampedY = clamp(mouseY, plotTop, plotBottom);
  const ratio = (clampedY - plotTop) / (plotBottom - plotTop);
  return yDomain[1] - ratio * (yDomain[1] - yDomain[0]);
}

function buildSelectionSummary(chart: AttributionChartResponse, start: string, end: string) {
  const ordered = orderSelection(start, end);
  const selectedPrices = chart.price_points.filter((point) => {
    const date = dateKey(point.date);
    return date >= ordered.start && date <= ordered.end;
  });
  if (selectedPrices.length < 2) {
    return null;
  }
  const first = selectedPrices[0];
  const last = selectedPrices[selectedPrices.length - 1];
  const priceChangePct = ((last.adjusted_close / first.adjusted_close) - 1) * 100;
  const selectedAttribution = chart.attribution_points.filter((point) => {
    const date = dateKey(point.window_end);
    return date >= ordered.start && date <= ordered.end;
  });
  return {
    start: dateKey(first.date),
    end: dateKey(last.date),
    priceChangePct,
    attributeShares: averageAttributeShares(selectedAttribution),
  };
}

function averageAttributeShares(points: AttributionChartPoint[]) {
  const totals = new Map<string, { name: string; total: number; count: number }>();
  for (const point of points) {
    for (const contribution of point.contributions) {
      if (contribution.share_of_move === null) {
        continue;
      }
      const key = `${contribution.driver}:${contribution.name}`;
      const current = totals.get(key) ?? { name: contribution.name, total: 0, count: 0 };
      current.total += contribution.share_of_move;
      current.count += 1;
      totals.set(key, current);
    }
  }
  return Array.from(totals.values())
    .map((item) => ({ name: item.name, averageShare: item.total / item.count }))
    .sort((left, right) => Math.abs(right.averageShare) - Math.abs(left.averageShare));
}

function orderSelection(start: string, end: string) {
  return start <= end ? { start, end } : { start: end, end: start };
}

function dateKey(value: string) {
  return value.slice(0, 10);
}

function driverDataKey(driver: string, side: "positive" | "negative" | "net") {
  return `driver_${side}_${driver}`;
}

function driverColor(driver: string) {
  return DRIVER_COLORS[driver] ?? FALLBACK_DRIVER_COLOR;
}

function formatDateTick(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function ChartHoverBox({
  row,
  driverOrder,
  displayMode,
  hover,
  bounds,
}: {
  row: ChartRow | null;
  driverOrder: string[];
  displayMode: DisplayMode;
  hover: HoverState;
  bounds: ChartBounds;
}) {
  if (!row) {
    return null;
  }
  const width = Math.min(
    POPUP_MAX_WIDTH,
    Math.max(POPUP_MIN_WIDTH, bounds.width - POPUP_GUTTER * 2),
  );
  const estimatedHeight = Math.min(POPUP_MAX_HEIGHT, 88 + driverOrder.length * 24);
  const maxLeft = Math.max(POPUP_GUTTER, bounds.width - width - POPUP_GUTTER);
  const prefersLeft = hover.mouseX > bounds.width / 2;
  const left = clamp(
    prefersLeft ? hover.mouseX - width - POPUP_OFFSET : hover.mouseX + POPUP_OFFSET,
    POPUP_GUTTER,
    maxLeft,
  );
  const top = clamp(
    hover.mouseY + POPUP_OFFSET,
    POPUP_GUTTER,
    Math.max(POPUP_GUTTER, bounds.height - estimatedHeight - POPUP_GUTTER),
  );
  const priceMovePct =
    typeof row.cumulative_return_pct === "number" ? row.cumulative_return_pct : null;
  const rows = buildHoverRows(row, driverOrder, priceMovePct);

  return (
    <div
      className="pointer-events-none absolute z-10 max-h-[300px] overflow-hidden rounded-[1rem] border border-[rgba(93,74,42,0.16)] bg-[#fffdf8]/88 px-3 py-2 text-xs shadow-[0_20px_40px_rgba(18,38,34,0.15)] backdrop-blur-sm"
      style={{ left, top, width }}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="font-semibold text-[#173f3a]">{formatDateTick(row.date)}</div>
        <div className="rounded-full border border-[rgba(23,63,58,0.10)] bg-white/55 px-2 py-0.5 text-[10px] font-semibold uppercase text-[#6b6256]">
          {displayMode === "bps" ? "bp" : "USD"}
        </div>
      </div>
      <div className="mt-1 text-[#23312f]">
        Price change: {formatPriceChange(row, displayMode)}
      </div>
      <div className="mt-2 space-y-1">
        {rows.map((item) => (
          <div
            key={item.driver}
            className={`grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2 rounded-[0.55rem] px-1.5 py-0.5 text-[#23312f] ${
              hover.activeDriver === item.driver ? "bg-white/70 font-bold" : "font-normal"
            }`}
          >
            <span
              className="h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: driverColor(item.driver) }}
            />
            <span className="truncate">{item.driver.replaceAll("_", " ")}</span>
            <span
              className="tabular-nums"
              style={{ color: item.share !== null && item.share < 0 ? "#a33b42" : "#2f7a62" }}
            >
              {formatShare(item.share)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function buildHoverRows(
  row: ChartRow,
  driverOrder: string[],
  priceMovePct: number | null,
) {
  const canComputeShare = typeof priceMovePct === "number" && Math.abs(priceMovePct) > NEAR_ZERO_PCT;
  return driverOrder
    .map((driver) => {
      const net = numberValue(row[driverDataKey(driver, "net")]);
      const share = canComputeShare && net !== null ? (net / priceMovePct) * 100 : null;
      return {
        driver,
        net: net ?? 0,
        share,
      };
    })
    .sort((left, right) => {
      const leftMagnitude = left.share === null ? Math.abs(left.net) : Math.abs(left.share);
      const rightMagnitude = right.share === null ? Math.abs(right.net) : Math.abs(right.share);
      return rightMagnitude - leftMagnitude;
    });
}

function numberValue(value: ChartRowValue | undefined) {
  return typeof value === "number" ? value : null;
}

function formatPriceChange(row: ChartRow, displayMode: DisplayMode) {
  if (displayMode === "usd") {
    return typeof row.price_change_usd === "number" ? formatSignedCurrency(row.price_change_usd) : "n/a";
  }
  return typeof row.cumulative_return_pct === "number"
    ? `${formatSignedNumber(row.cumulative_return_pct * 100, 1)} bp`
    : "n/a";
}

function formatShare(value: number | null) {
  return value === null ? "n/a" : `${formatSignedNumber(value, 1)}%`;
}

function formatSignedNumber(value: number, digits: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}`;
}

function formatSignedCurrency(value: number) {
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  return `${sign}$${Math.abs(value).toFixed(2)}`;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}
