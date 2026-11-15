// Phase 34. Renders a Phase-27 PositionCommand inside a simulation-or-live
// labelled card. The component's displayName is on the language-gate
// whitelist (`config/viza_command_language_gate.json`), so it may render
// BUY_TO_OPEN / TRIM_LONG / etc.; the language-gate test enforces that
// those words do NOT appear in any non-whitelisted component.

import type {
  InvestmentCommandPayload,
  PositionAxes,
} from "./radarTypes";
import type { VizaDecisionMode } from "./types";

interface DecisionCommandCardProps {
  command: InvestmentCommandPayload;
  mode: VizaDecisionMode;
  cutoffTimestamp: string;
  runId: string;
  evidenceChecksumPrefix: string;
}

export function DecisionCommandCard({
  command,
  mode,
  cutoffTimestamp,
  runId,
  evidenceChecksumPrefix,
}: DecisionCommandCardProps) {
  const axes = command.position_axes as PositionAxes;
  const isLive = mode === "live";
  return (
    <article
      className="decision-command-card"
      data-decision-command-iri={command.command_iri}
      data-argumentation-status={command.argumentation_status}
    >
      <header className="decision-command-card-header">
        <span
          className={
            isLive
              ? "decision-card-badge decision-card-badge-live"
              : "decision-card-badge decision-card-badge-sandbox"
          }
        >
          {isLive ? "Live" : "Sandbox replay"}
        </span>
        <span className="decision-command-card-label">{command.command_pref_label}</span>
        <span className="decision-command-card-target">
          {command.target.ticker_alias ?? command.target.entity_id}
        </span>
      </header>
      <dl className="decision-command-card-axes">
        <div>
          <dt>Direction</dt>
          <dd>{axes.direction}</dd>
        </div>
        <div>
          <dt>Position change</dt>
          <dd>{axes.position_change}</dd>
        </div>
        <div>
          <dt>Side</dt>
          <dd>{axes.side}</dd>
        </div>
        <div>
          <dt>Sizing method</dt>
          <dd>{command.sizing?.method ?? axes.default_sizing_method}</dd>
        </div>
        {command.resolved_sizing_value !== null ? (
          <div>
            <dt>Resolved size</dt>
            <dd>
              {formatSize(
                command.resolved_sizing_value,
                command.sizing?.units ?? "weight",
              )}
            </dd>
          </div>
        ) : null}
        <div>
          <dt>Confidence</dt>
          <dd>{command.command_confidence.toFixed(2)}</dd>
        </div>
        <div>
          <dt>Argumentation</dt>
          <dd>{command.argumentation_status}</dd>
        </div>
        <div>
          <dt>Execution routing</dt>
          <dd>none</dd>
        </div>
      </dl>
      {command.target.fibo_instrument_iri ? (
        <p className="decision-command-card-fibo">
          FIBO instrument: <code>{shortenIri(command.target.fibo_instrument_iri)}</code>
        </p>
      ) : null}
      <footer className="decision-command-card-footer">
        <span className="decision-command-card-disclaimer">
          Strategy-simulation output. Not investment advice. Not routed to any broker.
        </span>
        <span className="decision-command-card-audit">
          Cutoff {cutoffTimestamp} · Run {runId} · evidence{" "}
          {evidenceChecksumPrefix}
        </span>
      </footer>
    </article>
  );
}

DecisionCommandCard.displayName = "DecisionCommandCard";

function formatSize(value: number, units: string): string {
  if (units === "weight") {
    return `${(value * 100).toFixed(2)}%`;
  }
  if (units === "notional_usd") {
    return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  }
  return `${value} ${units}`;
}

function shortenIri(iri: string): string {
  if (!iri) return iri;
  if (iri.length <= 64) return iri;
  return `${iri.slice(0, 32)}…${iri.slice(-24)}`;
}
