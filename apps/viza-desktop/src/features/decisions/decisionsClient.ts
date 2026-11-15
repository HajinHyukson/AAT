import { VIZA_ENGINE_BASE_URL } from "../../vizaEngineClient";
import type {
  VizaDecisionsReplayRequest,
  VizaLiveDecisionsRequest,
  VizaLiveDecisionsResponse,
  VizaLiveModeOptInRecordRequest,
  VizaLiveModeStatus,
  VizaRunDecisionsResponse,
} from "./types";

/**
 * Typed error thrown when the engine surfaces a structured live-mode
 * precondition failure (HTTP 422). The ``code`` field comes from the
 * engine's exception class name so the desktop can route to the right
 * remediation flow deterministically.
 */
export class VizaLiveModeError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = "VizaLiveModeError";
    this.code = code;
  }
}

export function fetchRunDecisions(runId: string): Promise<VizaRunDecisionsResponse> {
  return decisionsRequestJson<VizaRunDecisionsResponse>(
    `/viza/runs/${encodeURIComponent(runId)}/decisions`,
  );
}

export function replayRunDecisions(
  runId: string,
  request: VizaDecisionsReplayRequest,
): Promise<VizaRunDecisionsResponse> {
  return decisionsRequestJson<VizaRunDecisionsResponse>(
    `/viza/runs/${encodeURIComponent(runId)}/decisions/replay`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(request),
    },
  );
}

export function fetchLiveModeStatus(): Promise<VizaLiveModeStatus> {
  return decisionsRequestJson<VizaLiveModeStatus>(
    "/viza/runtime/live-mode-status",
  );
}

export function recordLiveModeOptIn(
  profileId: string,
  request: VizaLiveModeOptInRecordRequest,
): Promise<Record<string, unknown>> {
  return decisionsRequestJson<Record<string, unknown>>(
    `/viza/profiles/${encodeURIComponent(profileId)}/live-mode-opt-in`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(request),
    },
  );
}

export function compileLiveDecisions(
  profileId: string,
  request: VizaLiveDecisionsRequest,
): Promise<VizaLiveDecisionsResponse> {
  return decisionsRequestJson<VizaLiveDecisionsResponse>(
    `/viza/profiles/${encodeURIComponent(profileId)}/decisions/live`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(request),
    },
  );
}

async function decisionsRequestJson<T>(path: string, init?: RequestInit): Promise<T> {
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
    const rawBody = await response.text();
    // Phase C.2: live-mode preconditions surface as HTTP 422 with a
    // structured FastAPI detail body `{detail: {code, message}}`. Parse
    // it into a typed VizaLiveModeError so the panel can branch on the
    // exception class name without resorting to regex on the message.
    if (response.status === 422 && rawBody) {
      try {
        const parsed: unknown = JSON.parse(rawBody);
        if (
          typeof parsed === "object" &&
          parsed !== null &&
          "detail" in parsed &&
          typeof (parsed as { detail: unknown }).detail === "object" &&
          (parsed as { detail: unknown }).detail !== null
        ) {
          const detailObject = (parsed as { detail: { code?: unknown; message?: unknown } }).detail;
          if (typeof detailObject.code === "string") {
            const codeMessage =
              typeof detailObject.message === "string"
                ? detailObject.message
                : detailObject.code;
            throw new VizaLiveModeError(detailObject.code, codeMessage);
          }
        }
      } catch (issue) {
        if (issue instanceof VizaLiveModeError) {
          throw issue;
        }
        // Fall through to generic Error on parse failure.
      }
    }
    throw new Error(
      `VIZA decisions API ${response.status}: ${rawBody || response.statusText}`,
    );
  }
  return (await response.json()) as T;
}
