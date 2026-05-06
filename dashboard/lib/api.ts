import type {
  AttributionChartRange,
  AttributionChartResponse,
  AttributionRun,
  ExposureUpdateDecision,
  UniverseResponse,
} from "./types";

export async function getLatestAttribution(ticker: string): Promise<AttributionRun> {
  const url = buildApiUrl("/attribution-runs/latest");
  url.searchParams.set("ticker", ticker);

  const response = await apiFetch(url);
  if (!response.ok) {
    throw new Error(`API returned ${response.status}`);
  }
  return response.json();
}

export async function getAttributionRuns(ticker: string, limit = 25): Promise<AttributionRun[]> {
  const url = buildApiUrl("/attribution-runs");
  url.searchParams.set("ticker", ticker);
  url.searchParams.set("limit", String(limit));

  const response = await apiFetch(url);
  if (!response.ok) {
    throw new Error(`API returned ${response.status}`);
  }
  return response.json();
}

export async function getAttributionRunById(runId: string): Promise<AttributionRun> {
  const url = buildApiUrl(`/attribution-runs/${runId}`);

  const response = await apiFetch(url);
  if (!response.ok) {
    throw new Error(`API returned ${response.status}`);
  }
  return response.json();
}

export async function getAttributionChart(
  ticker: string,
  range: AttributionChartRange,
): Promise<AttributionChartResponse> {
  const url = buildApiUrl("/attribution-chart");
  url.searchParams.set("ticker", ticker);
  url.searchParams.set("range", range);

  const response = await apiFetch(url);
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
  const url = buildApiUrl("/universe");
  for (const [key, value] of Object.entries(input)) {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  }

  const response = await apiFetch(url);
  if (!response.ok) {
    throw new Error(`API returned ${response.status}`);
  }
  return response.json();
}

export async function getExposureUpdateDecisions(
  ticker: string,
): Promise<ExposureUpdateDecision[]> {
  const url = buildApiUrl("/exposure-update-decisions");
  url.searchParams.set("ticker", ticker);

  const response = await apiFetch(url);
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
  const url = buildApiUrl("/analyst-feedback");

  const response = await apiFetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(`API returned ${response.status}`);
  }
  return response.json();
}

function buildApiUrl(path: string) {
  const baseUrl =
    typeof window === "undefined"
      ? process.env.AAT_API_BASE_URL ?? "http://127.0.0.1:8000"
      : `${window.location.origin}/api/aat`;
  const url = new URL(baseUrl);
  const basePath = url.pathname.replace(/\/$/, "");
  const apiPath = path.startsWith("/") ? path : `/${path}`;
  url.pathname = `${basePath}${apiPath}`;
  return url;
}

function apiFetch(url: URL, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  if (typeof window === "undefined" && process.env.AAT_API_KEY) {
    headers.set("x-aat-api-key", process.env.AAT_API_KEY);
  }

  return fetch(url, {
    ...init,
    headers,
    cache: "no-store",
  });
}
