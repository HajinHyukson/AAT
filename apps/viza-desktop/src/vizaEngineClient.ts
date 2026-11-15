import type {
  MethodologyRunResult,
  VizaBatchExecutionRequest,
  VizaBatchExecutionResult,
  VizaAttributeRegistry,
  VizaConnectorDefinition,
  VizaAlertDefinition,
  VizaAlertRecord,
  VizaEquityRuntimeWedgePreview,
  VizaEquityRuntimeWedgePreviewRequest,
  VizaEquityRuntimeWedgeStatus,
  VizaEquityPreviewPackageDraftRequest,
  VizaEquityPreviewPackageDraftResponse,
  VizaEquityPreviewReplayRequest,
  VizaEquityPreviewReplayResult,
  VizaEquityPreviewRunDetail,
  VizaEquityPreviewRunList,
  VizaMethodologyVersionDiff,
  VizaMethodologyVersionRecord,
  VizaMethodologyVersionSummary,
  VizaMethodologyGraph,
  VizaExportRequest,
  VizaExportResult,
  VizaProjectSummary,
  VizaRuntimeDiagnostics,
  VizaRunRecord,
  VizaRuntimeJobCreateRequest,
  VizaRuntimeJobEvent,
  VizaRuntimeJobRecord,
  VizaRuntimeScheduleRecord,
  VizaRuntimeScheduleRequest,
  VizaSavedRadarOutputRecord,
  VizaValidationRecord,
  VizaWatchlistRecord,
  VizaUniverseSummary,
} from "./vizaGraph";

const DEFAULT_ENGINE_BASE_URL = "http://127.0.0.1:8765";

export const VIZA_ENGINE_BASE_URL =
  import.meta.env.VITE_VIZA_ENGINE_URL ?? DEFAULT_ENGINE_BASE_URL;

interface EngineRequestConfig {
  baseUrl: string;
  token: string;
}

let engineRequestConfigPromise: Promise<EngineRequestConfig> | null = null;

export async function fetchVizaAttributes(): Promise<VizaAttributeRegistry> {
  return requestJson<VizaAttributeRegistry>("/viza/attributes");
}

export async function fetchVizaUniverses(): Promise<VizaUniverseSummary[]> {
  return requestJson<VizaUniverseSummary[]>("/viza/universes");
}

export async function fetchVizaConnectors(): Promise<VizaConnectorDefinition[]> {
  return requestJson<VizaConnectorDefinition[]>("/viza/connectors");
}

export async function fetchVizaDiagnostics(): Promise<VizaRuntimeDiagnostics> {
  return requestJson<VizaRuntimeDiagnostics>("/viza/diagnostics");
}

export async function fetchEquityRuntimeWedgeStatus(): Promise<VizaEquityRuntimeWedgeStatus> {
  return requestJson<VizaEquityRuntimeWedgeStatus>("/viza/equity/runtime-wedge/status");
}

export async function previewEquityRuntimeWedge(
  request: VizaEquityRuntimeWedgePreviewRequest,
): Promise<VizaEquityRuntimeWedgePreview> {
  return requestJson<VizaEquityRuntimeWedgePreview>("/viza/equity/runtime-wedge/preview", {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify(request),
  });
}

export async function fetchEquityPreviewRuns(
  params: {
    limit?: number;
    offset?: number;
    cik?: string;
    tickerAlias?: string;
    profileId?: string;
    status?: string;
  } = {},
): Promise<VizaEquityPreviewRunList> {
  const search = new URLSearchParams();
  if (params.limit !== undefined) {
    search.set("limit", String(params.limit));
  }
  if (params.offset !== undefined) {
    search.set("offset", String(params.offset));
  }
  if (params.cik) {
    search.set("cik", params.cik);
  }
  if (params.tickerAlias) {
    search.set("ticker_alias", params.tickerAlias);
  }
  if (params.profileId) {
    search.set("profile_id", params.profileId);
  }
  if (params.status) {
    search.set("status", params.status);
  }
  const query = search.toString() ? `?${search.toString()}` : "";
  return requestJson<VizaEquityPreviewRunList>(`/viza/equity/runtime-wedge/runs${query}`);
}

export async function fetchEquityPreviewRunDetail(runId: string): Promise<VizaEquityPreviewRunDetail> {
  return requestJson<VizaEquityPreviewRunDetail>(
    `/viza/equity/runtime-wedge/runs/${encodeURIComponent(runId)}`,
  );
}

export async function replayEquityPreviewRun(
  runId: string,
  request: VizaEquityPreviewReplayRequest,
): Promise<VizaEquityPreviewReplayResult> {
  return requestJson<VizaEquityPreviewReplayResult>(
    `/viza/equity/runtime-wedge/runs/${encodeURIComponent(runId)}/replay`,
    {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify(request),
    },
  );
}

export async function exportEquityPreviewPackageDraft(
  runId: string,
  request: VizaEquityPreviewPackageDraftRequest,
): Promise<VizaEquityPreviewPackageDraftResponse> {
  return requestJson<VizaEquityPreviewPackageDraftResponse>(
    `/viza/equity/runtime-wedge/runs/${encodeURIComponent(runId)}/package-draft`,
    {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify(request),
    },
  );
}

export async function fetchDefaultVizaProject(): Promise<VizaProjectSummary> {
  return requestJson<VizaProjectSummary>("/viza/projects/default");
}

export async function fetchVizaMethodologyVersions(
  methodologyId: string,
  projectId?: string,
): Promise<VizaMethodologyVersionSummary[]> {
  const search = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  return requestJson<VizaMethodologyVersionSummary[]>(
    `/viza/methodologies/${encodeURIComponent(methodologyId)}/versions${search}`,
  );
}

export async function fetchVizaMethodologyVersion(
  methodologyId: string,
  versionId: string,
): Promise<VizaMethodologyVersionRecord> {
  return requestJson<VizaMethodologyVersionRecord>(
    `/viza/methodologies/${encodeURIComponent(methodologyId)}/versions/${encodeURIComponent(
      versionId,
    )}`,
  );
}

export async function fetchVizaVersionDiff(
  methodologyId: string,
  leftVersionId: string,
  rightVersionId: string,
): Promise<VizaMethodologyVersionDiff> {
  const search = new URLSearchParams({
    left_version_id: leftVersionId,
    right_version_id: rightVersionId,
  });
  return requestJson<VizaMethodologyVersionDiff>(
    `/viza/methodologies/${encodeURIComponent(methodologyId)}/versions/compare?${search}`,
  );
}

export async function saveVizaMethodologyVersion({
  graph,
  label,
  message,
  parentVersionId,
  projectId,
}: {
  graph: VizaMethodologyGraph;
  label?: string;
  message?: string;
  parentVersionId?: string | null;
  projectId: string;
}): Promise<VizaMethodologyVersionRecord> {
  return requestJson<VizaMethodologyVersionRecord>(
    `/viza/projects/${encodeURIComponent(projectId)}/methodology-versions`,
    {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify({
        graph,
        label,
        message,
        parent_version_id: parentVersionId ?? null,
      }),
    },
  );
}

export async function executeMethodologyGraph(
  graph: VizaMethodologyGraph,
  options: { projectId?: string; methodologyVersionId?: string | null } = {},
): Promise<MethodologyRunResult> {
  const search = new URLSearchParams();
  if (options.projectId) {
    search.set("project_id", options.projectId);
  }
  if (options.methodologyVersionId) {
    search.set("methodology_version_id", options.methodologyVersionId);
  }
  const query = search.toString() ? `?${search.toString()}` : "";
  return requestJson<MethodologyRunResult>(`/viza/execute${query}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify(graph),
  });
}

export async function executeVizaBatch(
  request: VizaBatchExecutionRequest,
): Promise<VizaBatchExecutionResult> {
  return requestJson<VizaBatchExecutionResult>("/viza/batch/execute", {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify(request),
  });
}

export async function fetchVizaRunRecord(runId: string): Promise<VizaRunRecord> {
  return requestJson<VizaRunRecord>(`/viza/runs/${encodeURIComponent(runId)}`);
}

export async function createRuntimeJob(
  request: VizaRuntimeJobCreateRequest,
): Promise<VizaRuntimeJobRecord> {
  return requestJson<VizaRuntimeJobRecord>("/viza/jobs", {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify(request),
  });
}

export async function fetchRuntimeJob(jobId: string): Promise<VizaRuntimeJobRecord> {
  return requestJson<VizaRuntimeJobRecord>(`/viza/jobs/${encodeURIComponent(jobId)}`);
}

export async function cancelRuntimeJob(jobId: string): Promise<VizaRuntimeJobRecord> {
  return requestJson<VizaRuntimeJobRecord>(`/viza/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: "POST",
  });
}

export async function fetchRuntimeJobEvents(jobId: string): Promise<VizaRuntimeJobEvent[]> {
  return requestJson<VizaRuntimeJobEvent[]>(
    `/viza/jobs/${encodeURIComponent(jobId)}/events`,
  );
}

export async function saveVizaRadarOutput({
  projectId,
  result,
  name,
  selectedColumns,
  displayedTickers,
  designer,
  versionId,
}: {
  projectId: string;
  result: MethodologyRunResult;
  name?: string;
  selectedColumns: string[];
  displayedTickers: string[];
  designer: Record<string, unknown>;
  versionId?: string | null;
}): Promise<VizaSavedRadarOutputRecord> {
  return requestJson<VizaSavedRadarOutputRecord>(
    `/viza/projects/${encodeURIComponent(projectId)}/radars`,
    {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify({
        result,
        name,
        version_id: versionId ?? null,
        selected_columns: selectedColumns,
        displayed_tickers: displayedTickers,
        designer,
      }),
    },
  );
}

export async function saveVizaRadarSchedule({
  projectId,
  request,
}: {
  projectId: string;
  request: VizaRuntimeScheduleRequest;
}): Promise<VizaRuntimeScheduleRecord> {
  return requestJson<VizaRuntimeScheduleRecord>(
    `/viza/projects/${encodeURIComponent(projectId)}/schedules`,
    {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify(request),
    },
  );
}

export async function createVizaWatchlist({
  projectId,
  name,
  tickers,
  sourceRadarId,
  sourceRunId,
}: {
  projectId: string;
  name: string;
  tickers: string[];
  sourceRadarId?: string | null;
  sourceRunId?: string | null;
}): Promise<VizaWatchlistRecord> {
  return requestJson<VizaWatchlistRecord>(
    `/viza/projects/${encodeURIComponent(projectId)}/watchlists`,
    {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify({
        name,
        tickers,
        source_radar_id: sourceRadarId ?? null,
        source_run_id: sourceRunId ?? null,
      }),
    },
  );
}

export async function createVizaAlert({
  projectId,
  name,
  definition,
  enabled = true,
}: {
  projectId: string;
  name: string;
  definition: VizaAlertDefinition;
  enabled?: boolean;
}): Promise<VizaAlertRecord> {
  return requestJson<VizaAlertRecord>(
    `/viza/projects/${encodeURIComponent(projectId)}/alerts`,
    {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify({
        name,
        definition,
        enabled,
      }),
    },
  );
}

export async function exportVizaPayload(request: VizaExportRequest): Promise<VizaExportResult> {
  return requestJson<VizaExportResult>("/viza/exports", {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify(request),
  });
}

export async function createVizaValidationRecord(
  result: MethodologyRunResult,
): Promise<VizaValidationRecord> {
  return requestJson<VizaValidationRecord>("/viza/validation/record", {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify({ result }),
  });
}

export function resetVizaEngineRequestConfig(): void {
  engineRequestConfigPromise = null;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const config = await resolveEngineRequestConfig();
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
    throw new Error(`VIZA engine ${response.status}: ${detail || response.statusText}`);
  }
  return (await response.json()) as T;
}

async function resolveEngineRequestConfig(): Promise<EngineRequestConfig> {
  if (!window.vizaDesktop) {
    return {
      baseUrl: VIZA_ENGINE_BASE_URL,
      token: "",
    };
  }

  if (!engineRequestConfigPromise) {
    engineRequestConfigPromise = window.vizaDesktop.desktopStatus().then((status) => ({
      baseUrl: status.engineBaseUrl || VIZA_ENGINE_BASE_URL,
      token: status.engineToken || "",
    }));
  }

  return engineRequestConfigPromise;
}
