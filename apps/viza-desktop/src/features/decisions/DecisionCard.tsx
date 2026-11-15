import { useState } from "react";

import type { VizaDecisionFrame } from "./types";

interface DecisionCardProps {
  decision: VizaDecisionFrame;
}

export function DecisionCard({ decision }: DecisionCardProps) {
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const lookaheadLabel = labelForLookaheadRisk(decision.pit_state.lookahead_risk);
  const exportLabel = decision.source_rights_state.export_allowed
    ? "Source rights: export allowed"
    : "Source rights: export restricted";
  const isLive = decision.mode === "live";
  const badgeLabel = isLive ? "Live" : "Sandbox replay";
  const badgeClass = isLive
    ? "decision-card-badge decision-card-badge-live"
    : "decision-card-badge decision-card-badge-sandbox";
  return (
    <article className="decision-card" data-decision-id={decision.decision_id}>
      <header className="decision-card-header">
        <span className={badgeClass}>{badgeLabel}</span>
        <span className="decision-card-rule">{decision.rule_text}</span>
      </header>
      <p className="decision-card-action">{decision.action_template}</p>
      <dl className="decision-card-meta">
        <div>
          <dt>Entity</dt>
          <dd>{decision.entity_id}</dd>
        </div>
        <div>
          <dt>Cutoff (replay reference)</dt>
          <dd>{decision.cutoff_timestamp}</dd>
        </div>
        <div>
          <dt>Latest triggering observation</dt>
          <dd>{decision.pit_state.max_observation_available_at ?? "—"}</dd>
        </div>
        <div>
          <dt>Look-ahead risk</dt>
          <dd>{lookaheadLabel}</dd>
        </div>
        <div>
          <dt>Source rights</dt>
          <dd>{exportLabel}</dd>
        </div>
      </dl>
      <button
        className="decision-card-evidence-toggle"
        type="button"
        onClick={() => setEvidenceOpen((open) => !open)}
      >
        {evidenceOpen ? "Hide evidence chain" : "Show evidence chain"}
      </button>
      {evidenceOpen ? (
        <ul className="decision-card-evidence">
          {decision.trigger_observation_ids.map((observationId) => (
            <li key={observationId} className="decision-card-evidence-row">
              <span className="decision-card-evidence-label">Observation</span>
              <code>{observationId}</code>
            </li>
          ))}
        </ul>
      ) : null}
      <footer className="decision-card-footer">
        <span className="decision-card-disclaimer">
          Research-process flag from a user-authored rule. Not investment advice.
        </span>
        <span className="decision-card-audit">
          Run {decision.audit.run_id} · graph {decision.audit.graph_hash.slice(0, 8)} ·
          profile {decision.audit.profile_version.slice(0, 8)}
        </span>
      </footer>
    </article>
  );
}

function labelForLookaheadRisk(risk: string): string {
  switch (risk) {
    case "low":
      return "Low (all triggering observations available at or before cutoff)";
    case "warning":
      return "Warning";
    case "not_backtest_safe":
      return "Not backtest-safe";
    default:
      return risk;
  }
}
