// Phase 34 (`docs/viza_end_product/VIZA_INVESTMENT_COMMAND_IMPLEMENTATION_PLAN.md`).
// TypeScript projections of the Python Pydantic schemas that the Phase 27–33
// backend now emits. Kept in a dedicated file so the legacy `types.ts`
// surface stays minimal for the original DecisionsPanel callers.

export type CommandKind = "PositionCommand" | "AttentionCommand" | "SystemCommand";

export type Direction = "BUY" | "SELL" | "NONE";
export type PositionChange =
  | "OPEN"
  | "INCREASE"
  | "MAINTAIN"
  | "REDUCE"
  | "CLOSE"
  | "REBALANCE";
export type Side = "LONG" | "SHORT" | "FLAT";
export type SizingMethod =
  | "TARGET_WEIGHT"
  | "DELTA_WEIGHT"
  | "TARGET_NOTIONAL"
  | "DELTA_NOTIONAL"
  | "SHARES"
  | "IMPLICIT";
export type Urgency = "ELEVATED" | "EXCLUDE";
export type VetoKind = "EMIT_BLOCKED" | "EXPORT_BLOCKED" | "LIVE_MODE_BLOCKED";

export interface CanonicalIdentifier {
  scheme_iri: string;
  value: string;
}

export interface CommandTarget {
  entity_id: string;
  instrument_id: string | null;
  ticker_alias: string | null;
  fibo_legal_entity_iri: string | null;
  fibo_instrument_iri: string | null;
  identifier_set: CanonicalIdentifier[];
}

export interface PositionAxes {
  direction: Direction;
  position_change: PositionChange;
  side: Side;
  default_sizing_method: SizingMethod;
}

export interface AttentionAxes {
  urgency: Urgency;
}

export interface SystemAxes {
  veto_kind: VetoKind;
}

export interface SizingExpression {
  method: SizingMethod;
  expression: string;
  units: "weight" | "notional_usd" | "shares";
}

export interface Defeater {
  defeater_kind:
    | "evidence_absent"
    | "counter_event"
    | "time_decay"
    | "rights_blocked"
    | "pit_unsafe";
  window: string | null;
  required_evidence_keys: string[];
  countering_event_iris: string[];
  rationale: string | null;
}

export type ArgumentationStatus = "accepted" | "rejected" | "undecided";

export interface InvestmentCommandPayload {
  schema: "viza.investment_command.v1";
  command_iri: string;
  command_pref_label: string;
  kind: CommandKind;
  target: CommandTarget;
  position_axes: PositionAxes | null;
  attention_axes: AttentionAxes | null;
  system_axes: SystemAxes | null;
  sizing: SizingExpression | null;
  resolved_sizing_value: number | null;
  command_confidence: number;
  command_priority: number;
  defeaters: Defeater[];
  argumentation_status: ArgumentationStatus;
  argumentation_reason: string | null;
  execution_routing: "none";
  not_investment_advice: boolean;
}

export interface DecisionProvenance {
  decision_entity_iri: string;
  was_generated_by_run_iri: string;
  was_attributed_to_agent_iri: string;
  used_observation_iris: string[];
  used_event_iris: string[];
  used_insight_iris: string[];
  was_derived_from_iris: string[];
  graph_hash: string;
  profile_version: string;
  evidence_checksum: string;
  result_checksum: string | null;
}

export type RadarItemKind =
  | "ranking_result"
  | "decision_command"
  | "watch_command"
  | "blocked_command"
  | "package_warning";

export type RadarMode = "ranking_only" | "decisions_only" | "mixed";

export interface RankingRow {
  ticker: string;
  company_name: string | null;
  entity_id: string | null;
  asset_id: string | null;
  score: number | null;
  rank: number | null;
}

export interface RadarItem {
  schema: "viza.radar_item.v1";
  radar_item_id: string;
  item_kind: RadarItemKind;
  entity_id: string;
  asset_id: string | null;
  profile_id: string | null;
  source_run_id: string | null;
  source_object_id: string | null;
  display_group: string;
  priority: "low" | "medium" | "high";
  radar_score: number;
  sort_key: number;
  command_family_iri: string | null;
  command: InvestmentCommandPayload | null;
  ranking_row: RankingRow | null;
  pit_state: Record<string, unknown>;
  rights_state: Record<string, unknown>;
  validation_state: Record<string, unknown>;
  audit_chain: Record<string, unknown>;
  argumentation_status: ArgumentationStatus;
  render_component:
    | "RankingCard"
    | "DecisionCommandCard"
    | "WatchCommandCard"
    | "BlockedCommandCard"
    | "PackageWarningCard";
}

export interface OutputRadarView {
  schema: "viza.output_radar_view.v1";
  mode: RadarMode;
  hit_policy: string;
  item_counts_by_kind: Record<string, number>;
  item_counts_by_group: Record<string, number>;
  items: RadarItem[];
  not_investment_advice: boolean;
}
