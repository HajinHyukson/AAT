import { VIZA_ENGINE_BASE_URL } from "../../vizaEngineClient";
import type {
  StrategyProfileCreateRequest,
  StrategyProfileTemplateCatalog,
  VizaStrategyProfile,
} from "./types";

export function fetchStrategyProfileTemplates(): Promise<StrategyProfileTemplateCatalog> {
  return strategyProfileRequestJson<StrategyProfileTemplateCatalog>(
    "/viza/strategy-profile-templates",
  );
}

export function fetchStrategyProfiles(): Promise<VizaStrategyProfile[]> {
  return strategyProfileRequestJson<VizaStrategyProfile[]>("/viza/strategy-profiles");
}

export function createStrategyProfile(
  request: StrategyProfileCreateRequest,
): Promise<VizaStrategyProfile> {
  return strategyProfileRequestJson<VizaStrategyProfile>("/viza/strategy-profiles", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
}

export function cloneStrategyProfile(
  profileId: string,
  displayName?: string,
): Promise<VizaStrategyProfile> {
  return strategyProfileRequestJson<VizaStrategyProfile>(
    `/viza/strategy-profiles/${encodeURIComponent(profileId)}/clone`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ display_name: displayName ?? null }),
    },
  );
}

async function strategyProfileRequestJson<T>(path: string, init?: RequestInit): Promise<T> {
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
    throw new Error(`VIZA strategy profile API ${response.status}: ${detail || response.statusText}`);
  }
  return (await response.json()) as T;
}
