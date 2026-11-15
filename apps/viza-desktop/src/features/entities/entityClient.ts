import { VIZA_ENGINE_BASE_URL } from "../../vizaEngineClient";
import type { AssetResolveResult, EntityResolveResult, VizaAsset, VizaEntity } from "./types";

export function searchVizaEntities(query: string): Promise<VizaEntity[]> {
  return entityRequestJson<VizaEntity[]>(`/viza/entities/search?q=${encodeURIComponent(query)}`);
}

export function resolveVizaEntity(ticker: string): Promise<EntityResolveResult> {
  return entityRequestJson<EntityResolveResult>("/viza/entities/resolve", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ ticker }),
  });
}

export function searchVizaAssets(query: string): Promise<VizaAsset[]> {
  return entityRequestJson<VizaAsset[]>(`/viza/assets/search?q=${encodeURIComponent(query)}`);
}

export function resolveVizaAsset(ticker: string): Promise<AssetResolveResult> {
  return entityRequestJson<AssetResolveResult>("/viza/assets/resolve", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ ticker }),
  });
}

async function entityRequestJson<T>(path: string, init?: RequestInit): Promise<T> {
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
    throw new Error(`VIZA entity API ${response.status}: ${detail || response.statusText}`);
  }
  return (await response.json()) as T;
}
