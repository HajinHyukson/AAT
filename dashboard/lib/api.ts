import type {
  AttributionChartRange,
  AttributionChartResponse,
  AttributionRun,
  ExposureUpdateDecision,
  UniverseResponse,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function getLatestAttribution(ticker: string): Promise<AttributionRun> {
  const url = new URL("/attribution-runs/latest", API_BASE_URL);
  url.searchParams.set("ticker", ticker);
  url.searchParams.set("prefer_compose_port", "true");

  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`API returned ${response.status}`);
  }
  return response.json();
}

export async function getAttributionRuns(ticker: string, limit = 25): Promise<AttributionRun[]> {
  const url = new URL("/attribution-runs", API_BASE_URL);
  url.searchParams.set("ticker", ticker);
  url.searchParams.set("limit", String(limit));
  url.searchParams.set("prefer_compose_port", "true");

  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`API returned ${response.status}`);
  }
  return response.json();
}

export async function getAttributionRunById(runId: string): Promise<AttributionRun> {
  const url = new URL(`/attribution-runs/${runId}`, API_BASE_URL);
  url.searchParams.set("prefer_compose_port", "true");

  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`API returned ${response.status}`);
  }
  return response.json();
}

export async function getAttributionChart(
  ticker: string,
  range: AttributionChartRange,
): Promise<AttributionChartResponse> {
  const url = new URL("/attribution-chart", API_BASE_URL);
  url.searchParams.set("ticker", ticker);
  url.searchParams.set("range", range);
  url.searchParams.set("prefer_compose_port", "true");

  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`API returned ${response.status}`);
  }
  return response.json();
}

export async function getUniverse(input: {
  search?: string;
  sector?: string;
  industry?: string;
  exchange?: string;
  status?: string;
  sort?: string;
  order?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<UniverseResponse> {
  const url = new URL("/universe", API_BASE_URL);
  for (const [key, value] of Object.entries(input)) {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  }
  url.searchParams.set("prefer_compose_port", "true");

  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`API returned ${response.status}`);
  }
  return response.json();
}

export async function getExposureUpdateDecisions(
  ticker: string,
): Promise<ExposureUpdateDecision[]> {
  const url = new URL("/exposure-update-decisions", API_BASE_URL);
  url.searchParams.set("ticker", ticker);
  url.searchParams.set("prefer_compose_port", "true");

  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`API returned ${response.status}`);
  }
  return response.json();
}

export async function submitAnalystFeedback(input: {
  attribution_run_id: string;
  attribution_contribution_id?: string | null;
  feedback: "correct" | "partially_correct" | "wrong" | "missing_driver";
  missing_driver_name?: string | null;
  comment?: string | null;
}) {
  const url = new URL("/analyst-feedback", API_BASE_URL);
  url.searchParams.set("prefer_compose_port", "true");

  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(`API returned ${response.status}`);
  }
  return response.json();
}
