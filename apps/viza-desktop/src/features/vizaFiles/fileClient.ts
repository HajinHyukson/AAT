import { VIZA_ENGINE_BASE_URL } from "../../vizaEngineClient";
import type {
  VizaFileExportRequest,
  VizaFileExportResponse,
  VizaFileImportRequest,
  VizaFileImportResponse,
  VizaFileInspectionResult,
  VizaFileQuarantineResponse,
  VizaFileRecordResponse,
  VizaFileSectionsResponse,
  VizaFileValidationResult,
  VizaFileVisualization,
} from "./types";

interface VizaFileRequestConfig {
  baseUrl: string;
  token: string;
}

export function inspectVizaFile(path: string): Promise<VizaFileInspectionResult> {
  return requestVizaFileJson<VizaFileInspectionResult>("/viza/files/inspect", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ path }),
  });
}

export function validateVizaFile(path: string): Promise<VizaFileValidationResult> {
  return requestVizaFileJson<VizaFileValidationResult>("/viza/files/validate", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ path }),
  });
}

export function exportVizaFile(request: VizaFileExportRequest): Promise<VizaFileExportResponse> {
  return requestVizaFileJson<VizaFileExportResponse>("/viza/files/export", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
}

export function importVizaFile(request: VizaFileImportRequest): Promise<VizaFileImportResponse> {
  return requestVizaFileJson<VizaFileImportResponse>("/viza/files/import", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
}

export function fetchVizaFileRecord(fileId: string): Promise<VizaFileRecordResponse> {
  return requestVizaFileJson<VizaFileRecordResponse>(`/viza/files/${encodeURIComponent(fileId)}`);
}

export function fetchVizaFileRecords(): Promise<VizaFileRecordResponse[]> {
  return requestVizaFileJson<VizaFileRecordResponse[]>("/viza/files");
}

export function fetchVizaFileSections(fileId: string): Promise<VizaFileSectionsResponse> {
  return requestVizaFileJson<VizaFileSectionsResponse>(
    `/viza/files/${encodeURIComponent(fileId)}/sections`,
  );
}

export function fetchVizaFileVisualization(fileId: string): Promise<VizaFileVisualization> {
  return requestVizaFileJson<VizaFileVisualization>(
    `/viza/files/${encodeURIComponent(fileId)}/visualization`,
  );
}

export function quarantineVizaFile(
  fileId: string,
  reason: string,
): Promise<VizaFileQuarantineResponse> {
  return requestVizaFileJson<VizaFileQuarantineResponse>("/viza/files/quarantine", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ file_id: fileId, reason }),
  });
}

async function requestVizaFileJson<T>(path: string, init?: RequestInit): Promise<T> {
  const config = await resolveVizaFileRequestConfig();
  const headers = new Headers(init?.headers);
  if (config.token) {
    headers.set("x-viza-engine-token", config.token);
  }
  const response = await fetch(`${config.baseUrl}${path}`, {
    ...init,
    headers,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`VIZA file API ${response.status}: ${detail || response.statusText}`);
  }
  return (await response.json()) as T;
}

async function resolveVizaFileRequestConfig(): Promise<VizaFileRequestConfig> {
  if (!window.vizaDesktop) {
    return { baseUrl: VIZA_ENGINE_BASE_URL, token: "" };
  }
  const status = await window.vizaDesktop.desktopStatus();
  return {
    baseUrl: status.engineBaseUrl || VIZA_ENGINE_BASE_URL,
    token: status.engineToken || "",
  };
}
