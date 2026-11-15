import { VIZA_ENGINE_BASE_URL } from "../../vizaEngineClient";
import type {
  ModuleCompatibilityResult,
  ResolvedNodeType,
  VizaModuleManifest,
  VizaModuleRequirement,
} from "./types";

interface ModuleRequestConfig {
  baseUrl: string;
  token: string;
}

export async function fetchVizaModules(): Promise<VizaModuleManifest[]> {
  return requestModuleJson<VizaModuleManifest[]>("/viza/modules");
}

export async function fetchVizaModule(moduleId: string): Promise<VizaModuleManifest> {
  return requestModuleJson<VizaModuleManifest>(`/viza/modules/${encodeURIComponent(moduleId)}`);
}

export async function resolveVizaNodeTypes(typeIds: string[]): Promise<ResolvedNodeType[]> {
  return requestModuleJson<ResolvedNodeType[]>("/viza/modules/resolve-node-types", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ type_ids: typeIds }),
  });
}

export async function checkVizaModuleCompatibility(
  requiredModules: VizaModuleRequirement[],
): Promise<ModuleCompatibilityResult[]> {
  return requestModuleJson<ModuleCompatibilityResult[]>("/viza/modules/check-compatibility", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ required_modules: requiredModules }),
  });
}

async function requestModuleJson<T>(path: string, init?: RequestInit): Promise<T> {
  const config = await resolveModuleRequestConfig();
  const headers = new Headers(init?.headers);
  if (config.token) {
    headers.set("x-viza-engine-token", config.token);
  }
  const response = await fetch(`${config.baseUrl}${path}`, { ...init, headers });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`VIZA module API ${response.status}: ${detail || response.statusText}`);
  }
  return (await response.json()) as T;
}

async function resolveModuleRequestConfig(): Promise<ModuleRequestConfig> {
  if (!window.vizaDesktop) {
    return { baseUrl: VIZA_ENGINE_BASE_URL, token: "" };
  }
  const status = await window.vizaDesktop.desktopStatus();
  return {
    baseUrl: status.engineBaseUrl || VIZA_ENGINE_BASE_URL,
    token: status.engineToken || "",
  };
}
