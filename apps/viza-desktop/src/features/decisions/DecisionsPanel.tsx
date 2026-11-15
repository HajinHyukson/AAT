import { useCallback, useEffect, useState } from "react";

import { DecisionCard } from "./DecisionCard";
import { LiveModeOptInDialog } from "./LiveModeOptInDialog";
import {
  VizaLiveModeError,
  compileLiveDecisions,
  fetchLiveModeStatus,
  fetchRunDecisions,
  replayRunDecisions,
} from "./decisionsClient";
import type {
  VizaDecisionFrame,
  VizaDecisionMode,
  VizaLiveDecisionsResponse,
  VizaLiveModeStatus,
  VizaRunDecisionsResponse,
} from "./types";

interface DecisionsPanelProps {
  runId: string | null;
  liveModeProfileId?: string | null;
  liveModeGraphHash?: string;
  liveModeProfileVersion?: string;
  liveModeObservationIds?: string[];
}

export function DecisionsPanel({
  runId,
  liveModeProfileId,
  liveModeGraphHash,
  liveModeProfileVersion,
  liveModeObservationIds,
}: DecisionsPanelProps) {
  const [mode, setMode] = useState<VizaDecisionMode>("sandbox_replay");
  const [response, setResponse] = useState<
    VizaRunDecisionsResponse | VizaLiveDecisionsResponse | null
  >(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cutoffInput, setCutoffInput] = useState<string>("");
  const [liveStatus, setLiveStatus] = useState<VizaLiveModeStatus | null>(null);
  const [showOptInDialog, setShowOptInDialog] = useState(false);

  const loadSandboxDecisions = useCallback(async () => {
    if (!runId) {
      setResponse(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await fetchRunDecisions(runId);
      setResponse(result);
    } catch (issue) {
      setError(issue instanceof Error ? issue.message : String(issue));
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    if (mode === "sandbox_replay") {
      void loadSandboxDecisions();
    } else {
      // Live mode: fetch status to surface whether the engine env flag is on.
      void (async () => {
        try {
          const status = await fetchLiveModeStatus();
          setLiveStatus(status);
        } catch (issue) {
          setError(issue instanceof Error ? issue.message : String(issue));
        }
      })();
    }
  }, [mode, loadSandboxDecisions]);

  const onReplay = useCallback(async () => {
    if (!runId || !cutoffInput) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await replayRunDecisions(runId, {
        cutoff_timestamp: cutoffInput,
      });
      setResponse(result);
    } catch (issue) {
      setError(issue instanceof Error ? issue.message : String(issue));
    } finally {
      setLoading(false);
    }
  }, [runId, cutoffInput]);

  const onCompileLive = useCallback(async () => {
    if (
      !liveModeProfileId ||
      !liveModeGraphHash ||
      !liveModeProfileVersion ||
      !liveModeObservationIds
    ) {
      setError(
        "Live mode requires a profile ID, graph hash, profile version, and observation IDs.",
      );
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await compileLiveDecisions(liveModeProfileId, {
        graph_hash: liveModeGraphHash,
        profile_version: liveModeProfileVersion,
        observation_ids: liveModeObservationIds,
      });
      setResponse(result);
    } catch (issue) {
      // Phase C.2: the engine emits distinct exception classes for each
      // live-mode precondition failure (env flag, opt-in missing, opt-in
      // stale, rule effective_from missing). Route deterministically off
      // the structured ``code`` field rather than substring-matching the
      // message.
      if (issue instanceof VizaLiveModeError) {
        switch (issue.code) {
          case "LiveModeOptInRequiredError":
          case "LiveModeOptInStaleError":
            setShowOptInDialog(true);
            break;
          case "LiveModeDisabledError":
            setError(
              "Live mode is not enabled in this engine process. Set VIZA_LIVE_MODE_ENABLED=true and restart the engine.",
            );
            break;
          case "LiveModeRuleEffectiveDateRequiredError":
            setError(issue.message);
            break;
          default:
            setError(issue.message);
        }
      } else {
        setError(issue instanceof Error ? issue.message : String(issue));
      }
    } finally {
      setLoading(false);
    }
  }, [
    liveModeProfileId,
    liveModeGraphHash,
    liveModeProfileVersion,
    liveModeObservationIds,
  ]);

  const onOptInAccepted = () => {
    setShowOptInDialog(false);
    void onCompileLive();
  };

  const sandboxTitle = "Decisions (sandbox replay)";
  const liveTitle = "Decisions (live)";
  // eslint-disable-next-line max-len
  const sandboxHelp = "Each decision below is a deterministic firing of a user-authored rule against observations available at the run's cutoff timestamp. This view replays a stored run from observations already persisted in the project store.";
  // eslint-disable-next-line max-len
  const liveHelp = "Each decision below is a deterministic firing of a user-authored rule against the latest observations the engine pulled from the local project store at the moment the run was started. This is not investment advice.";

  if (mode === "sandbox_replay" && !runId) {
    return (
      <section className="decisions-panel">
        <div className="result-label">{sandboxTitle}</div>
        <div className="result-empty">
          Select a saved run to view its decisions.
        </div>
      </section>
    );
  }

  return (
    <section className="decisions-panel">
      <header className="decisions-panel-header">
        <div className="result-label">
          {mode === "live" ? liveTitle : sandboxTitle}
        </div>
        <span
          className={
            mode === "live"
              ? "decisions-panel-badge decisions-panel-badge-live"
              : "decisions-panel-badge decisions-panel-badge-sandbox"
          }
        >
          {mode === "live" ? "Live mode" : "Sandbox replay only"}
        </span>
      </header>

      <div className="decisions-panel-mode-selector" role="radiogroup" aria-label="Decision mode">
        <label>
          <input
            type="radio"
            name="decision-mode"
            value="sandbox_replay"
            checked={mode === "sandbox_replay"}
            onChange={() => setMode("sandbox_replay")}
          />
          Sandbox replay
        </label>
        <label>
          <input
            type="radio"
            name="decision-mode"
            value="live"
            checked={mode === "live"}
            onChange={() => setMode("live")}
          />
          Live mode
        </label>
      </div>

      <p className="decisions-panel-help">
        {mode === "live" ? liveHelp : sandboxHelp}
      </p>

      {mode === "live" && liveStatus && !liveStatus.enabled ? (
        <div className="decisions-panel-live-disabled">
          Live mode is not enabled in this engine. Set
          <code>{liveStatus.env_var}=true</code> and restart the engine to allow
          activation per profile.
        </div>
      ) : null}

      <div className="decisions-panel-controls">
        {mode === "sandbox_replay" ? (
          <>
            <label className="decisions-panel-cutoff-label">
              Replay cutoff (ISO timestamp)
              <input
                className="decisions-panel-cutoff-input"
                type="text"
                placeholder="2026-05-20T00:00:00+00:00"
                value={cutoffInput}
                onChange={(event) => setCutoffInput(event.target.value)}
              />
            </label>
            <button
              className="decisions-panel-replay-button"
              type="button"
              onClick={() => void onReplay()}
              disabled={loading || !cutoffInput}
            >
              Replay at cutoff
            </button>
            <button
              className="decisions-panel-reload-button"
              type="button"
              onClick={() => void loadSandboxDecisions()}
              disabled={loading}
            >
              Reload full history
            </button>
          </>
        ) : (
          <button
            className="decisions-panel-compile-live-button"
            type="button"
            onClick={() => void onCompileLive()}
            disabled={loading || !liveStatus?.enabled || !liveModeProfileId}
          >
            Compile live decisions
          </button>
        )}
      </div>

      {error ? (
        <div className="decisions-panel-error">{error}</div>
      ) : null}
      {loading ? (
        <div className="decisions-panel-loading">Loading decisions…</div>
      ) : null}
      {!loading && response ? (
        response.decisions.length > 0 ? (
          <div className="decisions-panel-list">
            {response.decisions.map((decision: VizaDecisionFrame) => (
              <DecisionCard key={decision.decision_id} decision={decision} />
            ))}
          </div>
        ) : (
          <div className="result-empty">
            No decisions were emitted for this run at the requested cutoff.
          </div>
        )
      ) : null}

      {showOptInDialog && liveModeProfileId && liveStatus ? (
        <LiveModeOptInDialog
          profileId={liveModeProfileId}
          status={liveStatus}
          onAccepted={onOptInAccepted}
          onCancelled={() => setShowOptInDialog(false)}
        />
      ) : null}
    </section>
  );
}
