import { VIZA_ENGINE_BASE_URL } from "../../vizaEngineClient";
import type {
  ObservationIngestRequest,
  ObservationQueryRequest,
  ObservationQueryResult,
  VizaObservation,
} from "./types";

export function queryVizaObservations(
  request: ObservationQueryRequest,
): Promise<ObservationQueryResult> {
  return observationRequestJson<ObservationQueryResult>("/viza/observations/query", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
}

export function getVizaObservation(observationId: string): Promise<VizaObservation> {
  return observationRequestJson<VizaObservation>(
    `/viza/observations/${encodeURIComponent(observationId)}`,
  );
}

export function ingestVizaObservations(
  request: ObservationIngestRequest,
): Promise<VizaObservation[]> {
  return observationRequestJson<VizaObservation[]>("/viza/observations/ingest", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
}

async function observationRequestJson<T>(path: string, init?: RequestInit): Promise<T> {
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
    throw new Error(`VIZA observation API ${response.status}: ${detail || response.statusText}`);
  }
  return (await response.json()) as T;
}
