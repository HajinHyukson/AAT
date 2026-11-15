// Phase 34. Renders an AttentionCommand (WATCH_CLOSELY / AVOID) — an
// attention-only flag with no sizing.

import type { InvestmentCommandPayload } from "./radarTypes";

interface WatchCommandCardProps {
  command: InvestmentCommandPayload;
}

export function WatchCommandCard({ command }: WatchCommandCardProps) {
  const urgency = command.attention_axes?.urgency ?? "ELEVATED";
  return (
    <article
      className="watch-command-card"
      data-decision-command-iri={command.command_iri}
    >
      <header className="watch-command-card-header">
        <span className="watch-command-card-badge">Attention</span>
        <span className="watch-command-card-label">{command.command_pref_label}</span>
        <span className="watch-command-card-target">
          {command.target.ticker_alias ?? command.target.entity_id}
        </span>
      </header>
      <dl className="watch-command-card-meta">
        <div>
          <dt>Urgency</dt>
          <dd>{urgency}</dd>
        </div>
        <div>
          <dt>Argumentation</dt>
          <dd>{command.argumentation_status}</dd>
        </div>
      </dl>
      <footer className="watch-command-card-footer">
        Attention flag emitted by the strategy. No position change. Not investment advice.
      </footer>
    </article>
  );
}

WatchCommandCard.displayName = "WatchCommandCard";
