import { VIZA_ENGINE_BASE_URL } from "../../vizaEngineClient";
import type { EventQueryRequest, EventQueryResult, ManualEventRequest, VizaEvent } from "./types";

export function queryVizaEvents(request: EventQueryRequest): Promise<EventQueryResult> {
  return eventRequestJson<EventQueryResult>("/viza/events/query", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
}

export function createManualVizaEvent(request: ManualEventRequest): Promise<VizaEvent> {
  return eventRequestJson<VizaEvent>("/viza/events/manual", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
}

export function getVizaEvent(eventId: string): Promise<VizaEvent> {
  return eventRequestJson<VizaEvent>(`/viza/events/${encodeURIComponent(eventId)}`);
}

async function eventRequestJson<T>(path: string, init?: RequestInit): Promise<T> {
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
    throw new Error(`VIZA event API ${response.status}: ${detail || response.statusText}`);
  }
  return (await response.json()) as T;
}
