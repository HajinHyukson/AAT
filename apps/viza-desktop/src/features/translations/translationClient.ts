import { VIZA_ENGINE_BASE_URL } from "../../vizaEngineClient";
import type { TranslationRequest, VizaTranslation } from "./types";

export function translateVizaInsight(request: TranslationRequest): Promise<VizaTranslation> {
  return translationRequestJson<VizaTranslation>("/viza/translate", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
}

export function fetchVizaTranslation(translationId: string): Promise<VizaTranslation> {
  return translationRequestJson<VizaTranslation>(
    `/viza/translations/${encodeURIComponent(translationId)}`,
  );
}

async function translationRequestJson<T>(path: string, init?: RequestInit): Promise<T> {
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
    throw new Error(`VIZA translation API ${response.status}: ${detail || response.statusText}`);
  }
  return (await response.json()) as T;
}
