export interface VizaDecisionAudit {
  graph_hash: string;
  profile_version: string;
  run_id: string;
  evidence_checksum: string;
}

export interface VizaDecisionPitState {
  cutoff_timestamp: string;
  max_observation_available_at: string | null;
  observation_count: number;
  lookahead_risk: "low" | "warning" | "not_backtest_safe" | string;
}

export interface VizaDecisionSourceRightsState {
  export_allowed: boolean;
  raw_snapshot_allowed: boolean;
  policies: Array<Record<string, unknown>>;
}

export type VizaDecisionMode = "sandbox_replay" | "live";

export interface VizaLiveModeOptIn {
  accepted_at: string;
  accepted_disclosure_version: string;
  accepted_by_user: string;
}

export interface VizaLiveModeStatus {
  enabled: boolean;
  env_var: string;
  disclosure_version: string;
  disclosure_text: string;
  non_advice_boundary: boolean;
}

export interface VizaLiveDecisionsRequest {
  graph_hash: string;
  profile_version: string;
  observation_ids: string[];
  run_id?: string | null;
  cutoff_timestamp?: string | null;
  persist?: boolean;
}

export interface VizaLiveModeOptInRecordRequest {
  accepted_disclosure_version: string;
  accepted_by_user: string;
}

export interface VizaDecisionFrame {
  schema: "viza.decision.v1";
  decision_id: string;
  strategy_profile_id: string;
  rule_id: string;
  entity_id: string;
  asset_id: string | null;
  action_template: string;
  rule_text: string;
  trigger_observation_ids: string[];
  pit_state: VizaDecisionPitState;
  source_rights_state: VizaDecisionSourceRightsState;
  cutoff_timestamp: string;
  mode: VizaDecisionMode;
  emitted_at: string;
  audit: VizaDecisionAudit;
  not_investment_advice: boolean;
}

export interface VizaLiveDecisionsResponse {
  run_id: string;
  cutoff_timestamp: string;
  decisions: VizaDecisionFrame[];
  count: number;
  mode: "live";
  validation_record_id: string;
  not_investment_advice: boolean;
}

export interface VizaRunDecisionsResponse {
  run_id: string;
  decisions: VizaDecisionFrame[];
  count: number;
  mode: VizaDecisionMode;
  not_investment_advice: boolean;
  cutoff_timestamp?: string;
}

export interface VizaDecisionsReplayRequest {
  cutoff_timestamp: string;
}
