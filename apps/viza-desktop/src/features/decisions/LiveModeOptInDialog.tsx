import { useState } from "react";

import { recordLiveModeOptIn } from "./decisionsClient";
import type { VizaLiveModeStatus } from "./types";

interface LiveModeOptInDialogProps {
  profileId: string;
  status: VizaLiveModeStatus;
  defaultUserIdentifier?: string;
  onAccepted: () => void;
  onCancelled: () => void;
}

export function LiveModeOptInDialog({
  profileId,
  status,
  defaultUserIdentifier,
  onAccepted,
  onCancelled,
}: LiveModeOptInDialogProps) {
  const [acknowledged, setAcknowledged] = useState(false);
  const [userIdentifier, setUserIdentifier] = useState(
    defaultUserIdentifier ?? "self",
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onAccept = async () => {
    if (!acknowledged) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await recordLiveModeOptIn(profileId, {
        accepted_disclosure_version: status.disclosure_version,
        accepted_by_user: userIdentifier || "self",
      });
      onAccepted();
    } catch (issue) {
      setError(issue instanceof Error ? issue.message : String(issue));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="live-mode-opt-in-overlay" role="dialog" aria-modal="true">
      <section className="live-mode-opt-in-card">
        <header className="live-mode-opt-in-header">
          <h2>Activate live mode</h2>
          <span className="live-mode-opt-in-version">
            Disclosure version {status.disclosure_version}
          </span>
        </header>
        <pre className="live-mode-opt-in-disclosure">{status.disclosure_text}</pre>
        <label className="live-mode-opt-in-acknowledgement">
          <input
            type="checkbox"
            checked={acknowledged}
            onChange={(event) => setAcknowledged(event.target.checked)}
          />
          I understand this is not investment advice and I am activating
          deterministic firings of my own authored rules.
        </label>
        <label className="live-mode-opt-in-identifier">
          Recorded against identifier
          <input
            type="text"
            value={userIdentifier}
            onChange={(event) => setUserIdentifier(event.target.value)}
            placeholder="self"
          />
        </label>
        {error ? (
          <div className="live-mode-opt-in-error">{error}</div>
        ) : null}
        <footer className="live-mode-opt-in-footer">
          <button
            type="button"
            className="live-mode-opt-in-cancel"
            onClick={onCancelled}
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            type="button"
            className="live-mode-opt-in-accept"
            onClick={() => void onAccept()}
            disabled={!acknowledged || submitting}
          >
            {submitting ? "Recording…" : "Record opt-in"}
          </button>
        </footer>
      </section>
    </div>
  );
}
