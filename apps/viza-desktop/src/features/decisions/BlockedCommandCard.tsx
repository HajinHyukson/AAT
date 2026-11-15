// Phase 34. Renders a SystemCommand veto (BLOCK_ACTION / BLOCK_EXPORT)
// emitted by the engine when PIT, rights, validation, or live-mode
// preconditions fail. Whitelisted to render the command label per
// `config/viza_command_language_gate.json`.

import type { Defeater, InvestmentCommandPayload } from "./radarTypes";

interface BlockedCommandCardProps {
  command: InvestmentCommandPayload;
  rationale?: string | null;
}

export function BlockedCommandCard({ command, rationale }: BlockedCommandCardProps) {
  const reason = rationale ?? command.argumentation_reason ?? "Veto emitted by guard rule.";
  return (
    <article
      className="blocked-command-card"
      data-decision-command-iri={command.command_iri}
    >
      <header className="blocked-command-card-header">
        <span className="blocked-command-card-badge">System veto</span>
        <span className="blocked-command-card-label">{command.command_pref_label}</span>
        <span className="blocked-command-card-target">
          {command.target.ticker_alias ?? command.target.entity_id}
        </span>
      </header>
      <p className="blocked-command-card-reason">{reason}</p>
      {command.defeaters.length > 0 ? (
        <ul className="blocked-command-card-defeaters">
          {command.defeaters.map((defeater: Defeater, index: number) => (
            <li
              key={`${defeater.defeater_kind}-${index}`}
              className="blocked-command-card-defeater"
            >
              <strong>{defeater.defeater_kind}</strong>
              {defeater.rationale ? <span>: {defeater.rationale}</span> : null}
            </li>
          ))}
        </ul>
      ) : null}
      <footer className="blocked-command-card-footer">
        <span>
          Execution routing: none. The engine refused to emit a position command.
        </span>
      </footer>
    </article>
  );
}

BlockedCommandCard.displayName = "BlockedCommandCard";
