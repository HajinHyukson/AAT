import { VIZA_ENGINE_BASE_URL } from "../../vizaEngineClient";
import type { VizaInsightCardPayload } from "../../vizaGraph";
import type { InsightQueryRequest, InsightQueryResult, VizaInsight } from "./types";

export function queryVizaInsights(request: InsightQueryRequest): Promise<InsightQueryResult> {
  return insightRequestJson<InsightQueryResult>("/viza/insights/query", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
}

export function getVizaInsight(insightId: string): Promise<VizaInsight> {
  return insightRequestJson<VizaInsight>(`/viza/insights/${encodeURIComponent(insightId)}`);
}

export function fetchRunInsightCards(runId: string): Promise<VizaInsightCardPayload[]> {
  return insightRequestJson<VizaInsightCardPayload[]>(
    `/viza/runs/${encodeURIComponent(runId)}/insight-cards`,
  );
}

async function insightRequestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const status = window.vizaDesktop ? await window.vizaDesktop.desktopStatus() : null;
  const headers = new Headers(init?.headers);
  if (status?.engineToken) {
    headers.set("x-viza-engine-token", status.engineToken);
  }
  const response = await fetch(`${status?.engineBaseUrl || VIZA_ENGINE_BASE_URL}${path}`, {
    ...init,
    headers,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`VIZA insight API ${response.status}: ${detail || response.statusText}`);
  }
  return (await response.json()) as T;
}
