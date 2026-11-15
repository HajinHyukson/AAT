export const VIZA_GRAPH_SCHEMA_VERSION = "viza_graph_v0" as const;
export const VIZA_ATTRIBUTE_REGISTRY_SCHEMA_VERSION = "viza_attribute_registry_v1" as const;

export const VIZA_NODE_TYPES = [
  "universe",
  "attribute",
  "transform",
  "filter",
  "score",
  "relationship",
  "output_radar",
] as const;

export const VIZA_EDGE_TYPES = ["data_flow", "relationship", "evidence"] as const;

export type VizaNodeType = (typeof VIZA_NODE_TYPES)[number];
export type VizaEdgeType = (typeof VIZA_EDGE_TYPES)[number];

export interface VizaPosition {
  x: number;
  y: number;
}

export interface VizaGraphNode {
  id: string;
  type: VizaNodeType;
  position: VizaPosition;
  label?: string | null;
  config: Record<string, unknown>;
}

export interface VizaGraphEdge {
  id: string;
  source: string;
  target: string;
  type: VizaEdgeType;
  config?: Record<string, unknown>;
}

export interface VizaMethodologyGraph {
  schema_version: typeof VIZA_GRAPH_SCHEMA_VERSION;
  methodology_id: string;
  name: string;
  description?: string | null;
  created_at: string;
  updated_at: string;
  nodes: VizaGraphNode[];
  edges: VizaGraphEdge[];
  metadata?: Record<string, unknown>;
}

export interface VizaAttributeDefinition {
  key: string;
  display_name: string;
  family: string;
  description: string;
  unit: string;
  source: string;
  source_type?: string;
  frequency?: string;
  coverage?: string;
  coverage_universe?: string;
  freshness?: string;
  timestamp_policy?: string;
  availability_function: string;
  point_in_time_status: string;
  contribution_stage: string;
  evidence_policy: string;
  license_policy: string;
  entitlement_policy?: string;
  cache_policy?: string;
  production_scoring_allowed?: boolean;
  evidence_only?: boolean;
  allowed_transforms?: string[];
  compatible_node_types?: string[];
  diagnostics?: Record<string, unknown>;
  limitations?: string[];
  owner?: string;
  model_version?: string;
  data_version?: string;
  deprecation_status?: string;
}

export interface VizaAttributeRegistry {
  schema_version: typeof VIZA_ATTRIBUTE_REGISTRY_SCHEMA_VERSION;
  registry_version?: string;
  description: string;
  attributes: VizaAttributeDefinition[];
}

export interface VizaUniverseSummary {
  key: string;
  universe_name: string;
  version: string;
  display_name: string;
  source: string;
  asset_count: number;
  timestamp_available: string | null;
  config_path: string;
  sample_tickers: string[];
}

export interface VizaEntitlementPolicy {
  policy_label: string;
  query_allowed: boolean;
  local_cache_allowed: boolean;
  raw_snapshot_allowed: boolean;
  derived_value_allowed: boolean;
  export_allowed: boolean;
  redistribution_allowed: boolean;
  expires_at: string | null;
  attribution_required: boolean;
  user_credential_required: boolean;
  organization_credential_required: boolean;
  limitations: string[];
}

export interface VizaCredentialRequirement {
  key: string;
  display_name: string;
  required: boolean;
  storage: string;
  env_var: string | null;
  configured: boolean;
  secret_available: boolean;
}

export interface VizaConnectorDefinition {
  connector_id: string;
  display_name: string;
  source_type: string;
  status: string;
  description: string;
  capabilities: string[];
  credential_requirements: VizaCredentialRequirement[];
  license_policy: string;
  cache_policy: string;
  entitlement: VizaEntitlementPolicy;
  diagnostics: Record<string, unknown>;
}

export interface VizaDiagnosticCheck {
  name: string;
  status: string;
  message: string;
  detail: Record<string, unknown>;
}

export interface VizaProjectStoreDiagnostics {
  path: string;
  status: string;
  directory_exists: boolean;
  directory_writable: boolean;
  database_exists: boolean;
  schema_tables: string[];
  missing_tables: string[];
  project_count: number;
  methodology_version_count: number;
  run_count: number;
  last_run_id: string | null;
  last_run_status: string | null;
  last_run_created_at: string | null;
  error: string | null;
}

export interface VizaConnectorRuntimeStatus {
  connector_id: string;
  display_name: string;
  status: string;
  source_type: string;
  credential_required: boolean;
  credentials_configured: boolean;
  credential_mode: string;
  query_allowed: boolean;
  cache_allowed: boolean;
  display_allowed: boolean;
  export_allowed: boolean;
  redistribution_allowed: boolean;
  license_policy: string;
  cache_policy: string;
}

export interface VizaConfigFileStatus {
  path: string;
  resolved_path: string;
  exists: boolean;
}

export interface VizaRuntimeDiagnostics {
  service: string;
  status: string;
  engine_version: string;
  diagnostics_version: string;
  python_version: string;
  platform: string;
  cwd: string;
  package_root: string;
  config_root: string;
  config_files: VizaConfigFileStatus[];
  token_required: boolean;
  attribute_registry_schema_version: string;
  attribute_registry_version: string;
  attribute_count: number;
  project_store: VizaProjectStoreDiagnostics;
  connector_statuses: VizaConnectorRuntimeStatus[];
  file_format_version: string;
  installed_modules: Array<Record<string, unknown>>;
  credential_mode: string;
  observation_store_health: Record<string, unknown>;
  viza_file_health: Record<string, unknown>;
  last_quarantine_event: Record<string, unknown>;
  source_backed_resolver_count: number;
  prototype_fallback_count: number;
  credential_ready_connector_count: number;
  observation_store_status: string;
  last_resolver_warning_count: number;
  checks: VizaDiagnosticCheck[];
}

export interface VizaProjectSummary {
  project_id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
  methodology_count: number;
}

export interface VizaEquityPreviewTargetRequest {
  cik?: string | null;
  ticker_alias?: string | null;
}

export interface VizaEquityRuntimeWedgePreviewRequest {
  target: VizaEquityPreviewTargetRequest;
  profile_id: string;
  package_mode: "white_box" | "output_only" | "marketplace_draft";
  include_fmp: boolean;
  include_fred: boolean;
  use_live_connectors: boolean;
  cutoff_timestamp?: string | null;
  mock_fixture_id?: string;
  persist_run?: boolean;
}

export interface VizaEquityRuntimeWedgeStatus {
  module_id: string;
  module_version: string;
  enabled: boolean;
  feature_flags: {
    runtime_handlers_enabled: boolean;
    sec_wedge_enabled: boolean;
    fmp_enabled: boolean;
    fred_enabled: boolean;
    live_integration_tests_enabled: boolean;
    preview_persistence_enabled: boolean;
    preview_replay_refresh_enabled: boolean;
  };
  mock_fixture_default: boolean;
  mock_fixture_id: string;
  profile_id: string;
  package_modes: Array<"white_box" | "output_only" | "marketplace_draft">;
  live_mode_allowed: boolean;
  persistence_enabled: boolean;
  replay_refresh_enabled: boolean;
}

export interface VizaEquityPreviewDecision {
  source: string | null;
  reason?: string | null;
  warnings?: string[];
  source_ids?: string[];
}

export interface VizaEquityRuntimeWedgePreview {
  module_id: string;
  module_version: string;
  feature_flags: VizaEquityRuntimeWedgeStatus["feature_flags"];
  target: {
    entity_id: string | null;
    company_id: string | null;
    security_id: string | null;
    cik: string | null;
    ticker_alias: string | null;
    display_name: string;
    primary_key_policy?: string | null;
  };
  profile: {
    profile_id: string;
    compatibility_status: "pass" | "warn" | "block";
    warnings: Array<Record<string, unknown>>;
    blocks: Array<Record<string, unknown>>;
  };
  evidence_summary: {
    source_count: number;
    sources: Array<Record<string, unknown>>;
    filing_refs: Array<Record<string, unknown>>;
    observed_at: string;
    available_at: string;
    retrieved_at: string;
  };
  fundamental_attributes: Array<Record<string, unknown>>;
  optional_market_context: {
    fmp: {
      enabled: boolean;
      status: string;
      rights_status: string;
      values_redacted: boolean;
      warnings?: string[];
    };
    fred: {
      enabled: boolean;
      status: string;
      pit_status: string;
      values_redacted: boolean;
      warnings?: string[];
    };
  };
  output_preview: {
    view_id: string;
    non_advice_boundary: string;
    summary_cards: Array<Record<string, unknown>>;
    missing_data_warnings: string[];
  };
  validation_report: {
    status: "pass" | "warn" | "block";
    rules: Array<Record<string, unknown>>;
  };
  source_rights_report: {
    status: "pass" | "warn" | "block";
    policies: Array<Record<string, unknown>>;
  };
  package_redaction_preview: {
    package_mode: "white_box" | "output_only" | "marketplace_draft";
    included: VizaEquityPreviewDecision[];
    redacted: VizaEquityPreviewDecision[];
    blocked: VizaEquityPreviewDecision[];
    external_references: VizaEquityPreviewDecision[];
    entitlement_locked: VizaEquityPreviewDecision[];
  };
  audit: {
    run_id: string;
    graph_hash: string;
    profile_hash: string;
    proof_checksum: string;
    fixture_mode: boolean;
  };
  run_id?: string;
  persisted?: boolean;
  persistence_status?: "persisted" | "disabled" | "failed" | "skipped" | "replay_created";
  history_url?: string;
  proof_checksum?: string;
}

export interface VizaEquityPreviewRunSummary {
  run_id: string;
  created_at: string;
  target_display_name: string;
  cik: string | null;
  ticker_alias: string | null;
  profile_id: string;
  status: "pass" | "warn" | "block" | "failed";
  package_mode: "white_box" | "output_only" | "marketplace_draft";
  pit_status: "pass" | "warn" | "block";
  rights_status: "pass" | "warn" | "block";
  validation_status: "pass" | "warn" | "block";
  proof_checksum: string;
}

export interface VizaEquityPreviewRunList {
  runs: VizaEquityPreviewRunSummary[];
  total: number;
}

export interface VizaEquityPreviewRunDetail {
  run_record: Record<string, unknown>;
  target: Record<string, unknown>;
  evidence_bundle: Record<string, unknown>;
  observations: Array<Record<string, unknown>>;
  output_preview: Record<string, unknown>;
  validation_report: {
    status?: "pass" | "warn" | "block";
    rules?: Array<Record<string, unknown>>;
  };
  source_rights_report: {
    status?: "pass" | "warn" | "block";
    policies?: Array<Record<string, unknown>>;
  };
  package_redaction_preview: {
    package_mode?: "white_box" | "output_only" | "marketplace_draft";
    included?: VizaEquityPreviewDecision[];
    redacted?: VizaEquityPreviewDecision[];
    blocked?: VizaEquityPreviewDecision[];
    external_references?: VizaEquityPreviewDecision[];
    entitlement_locked?: VizaEquityPreviewDecision[];
  };
  audit: Record<string, unknown>;
}

export interface VizaEquityPreviewReplayRequest {
  mode: "replay_from_stored_observations" | "replay_with_refresh";
  package_mode?: "white_box" | "output_only" | "marketplace_draft" | null;
  include_fmp: boolean;
  include_fred: boolean;
}

export interface VizaEquityPreviewReplayResult {
  mode: string;
  parent_run_id: string;
  run_id: string;
  preview: VizaEquityRuntimeWedgePreview;
  differences: Array<Record<string, unknown>>;
}

export interface VizaEquityPreviewPackageDraftRequest {
  package_mode: "white_box" | "output_only" | "marketplace_draft";
  target_path?: string | null;
  project_id?: string | null;
  creator_id?: string | null;
  creator_display_name?: string | null;
  not_investment_advice_acknowledged?: boolean;
}

export interface VizaEquityPreviewPackageDraftResponse {
  run_id: string;
  package_mode: "white_box" | "output_only" | "marketplace_draft";
  package_ready_status: string;
  target_path: string;
  result: Record<string, unknown>;
  manifest: Record<string, unknown>;
  export_record: Record<string, unknown> | null;
  proof_checksum: string;
  pit_summary: Record<string, unknown>;
  rights_summary: Record<string, unknown>;
  package_redaction_preview: VizaEquityRuntimeWedgePreview["package_redaction_preview"];
  non_advice_boundary: string;
  warnings: string[];
}

export interface VizaMethodologyVersionSummary {
  version_id: string;
  project_id: string;
  methodology_id: string;
  name: string;
  label: string | null;
  message: string | null;
  schema_version: string;
  graph_hash: string;
  parent_version_id: string | null;
  created_at: string;
  updated_at: string;
  graph_created_at: string;
  graph_updated_at: string;
  node_count: number;
  edge_count: number;
}

export interface VizaMethodologyVersionRecord extends VizaMethodologyVersionSummary {
  graph: VizaMethodologyGraph;
}

export interface VizaMethodologyVersionDiff {
  left_version_id: string;
  right_version_id: string;
  left_graph_hash: string;
  right_graph_hash: string;
  added_nodes: string[];
  removed_nodes: string[];
  changed_nodes: string[];
  added_edges: string[];
  removed_edges: string[];
  changed_edges: string[];
  metadata_changed: boolean;
}

export type VizaExecutionStatus = "completed" | "not_implemented" | "failed";

export interface VizaExecutionWarning {
  code: string;
  message: string;
  node_id: string | null;
  severity: string;
}

export interface VizaRadarRow {
  ticker: string;
  company_name: string | null;
  entity_id?: string | null;
  asset_id?: string | null;
  score: number | null;
  rank: number | null;
  attributes: Record<string, number | string | boolean | null>;
  strategy_fit_score?: number | null;
  primary_insight_type?: string | null;
  translated_summary?: string | null;
  confidence?: number | null;
  horizon?: Record<string, string> | null;
  missing_confirmations?: string[];
  invalidation_conditions?: string[];
  risk_flags?: string[];
  evidence_count?: number;
  source_restrictions?: string[];
  PIT_status?: string | null;
  warnings: string[];
  evidence_refs: string[];
}

export interface VizaRelationshipEdge {
  relationship_id?: string | null;
  source: string;
  target: string;
  source_id?: string | null;
  source_type?: string | null;
  target_id?: string | null;
  target_type?: string | null;
  family?: string | null;
  relationship_type: string;
  relationship_family: string;
  weight: number | null;
  direction: string;
  confidence: number | null;
  time_horizon?: string | null;
  observed_at?: string | null;
  available_at?: string | null;
  timestamp_available: string | null;
  evidence_ref: string | null;
  evidence_refs?: string[];
  rights_policy?: Record<string, unknown>;
  module_id?: string | null;
  source_lineage: Record<string, unknown>;
  diagnostics: Record<string, unknown>;
}

export interface VizaInsight {
  schema: "viza.insight.v1";
  insight_id: string;
  entity_id: string;
  asset_id: string | null;
  related_entity_ids: string[];
  related_asset_ids: string[];
  insight_type: string;
  direction: string;
  magnitude: Record<string, unknown> | null;
  confidence: number;
  time_horizon: Record<string, string>;
  evidence_refs: string[];
  source_policy: Record<string, unknown>;
  observed_at: string;
  available_at: string;
  generated_at: string;
  strategy_compatibility: Array<Record<string, unknown>>;
  risk_factors: string[];
  invalidation_conditions: string[];
  action_layer: Record<string, unknown>;
  derivation_trace: Record<string, unknown>;
}

export interface VizaTranslation {
  schema: "viza.translation.v1";
  translation_id: string;
  insight_id: string;
  strategy_profile_id: string;
  entity_id: string;
  asset_id: string | null;
  fit_score: number;
  relevance: string;
  translated_summary: string;
  strategy_fit_reasons: string[];
  missing_confirmations: string[];
  risk_factors: string[];
  invalidation_conditions: string[];
  suggested_research_action: string;
  evidence_refs: string[];
  generated_at: string;
  not_investment_advice: boolean;
}

export interface VizaInsightCardEvidence {
  evidence_ref: string;
  source: string;
  observed_at: string | null;
  available_at: string | null;
  source_credibility: number | null;
  license_policy: string;
  export_status: string;
  redacted: boolean;
}

export interface VizaInsightCardRelationship {
  relationship_id: string;
  source: string;
  target: string;
  relationship_family: string;
  relationship_type: string;
  direction: string;
  confidence: number | null;
  evidence_ref: string | null;
}

export interface VizaInsightCardAudit {
  graph_hash: string;
  profile_version: string | null;
  run_id: string;
  evidence_checksum: string;
  result_checksum: string;
}

export interface VizaInsightCardPayload {
  insight_id: string;
  entity_id: string;
  asset_id: string | null;
  insight_type: string;
  direction: string;
  confidence: number;
  horizon: Record<string, string>;
  strategy_fit_score: number | null;
  translated_summary: string | null;
  strategy_fit_reasons: string[];
  missing_confirmations: string[];
  invalidation_conditions: string[];
  risk_factors: string[];
  suggested_research_action: string | null;
  evidence: VizaInsightCardEvidence[];
  relationships: VizaInsightCardRelationship[];
  audit: VizaInsightCardAudit;
}

export interface VizaNodeExecutionResult {
  node_id: string;
  node_type: string;
  status: string;
  output_ref: string | null;
  warnings: string[];
  evidence_refs: string[];
  diagnostics: Record<string, unknown>;
  started_at: string;
  finished_at: string;
}

export interface MethodologyRunResult {
  run_id: string;
  methodology_id: string;
  graph_hash: string;
  status: VizaExecutionStatus;
  timestamp_cutoff: string | null;
  result_checksum: string;
  rows: VizaRadarRow[];
  relationships: VizaRelationshipEdge[];
  insights: VizaInsight[];
  insight_relationships: VizaRelationshipEdge[];
  translations: VizaTranslation[];
  warnings: VizaExecutionWarning[];
  node_results: VizaNodeExecutionResult[];
  evidence: Record<string, unknown>;
  manifest: Record<string, unknown>;
}

export interface VizaRunRecord {
  run_id: string;
  project_id: string | null;
  methodology_id: string;
  version_id: string | null;
  graph_hash: string;
  status: string;
  result_checksum: string;
  created_at: string;
  manifest: Record<string, unknown>;
  result: MethodologyRunResult | null;
}

export interface VizaValidationRecord {
  schema: "viza.validation_record.v1";
  validation_record_id: string;
  strategy_or_methodology_id: string;
  strategy_profile_id: string | null;
  run_id: string;
  graph_hash: string;
  result_checksum: string;
  timestamp_cutoff: string | null;
  generated_at: string;
  domain: string;
  module_id: string;
  entity_universe: Record<string, unknown>;
  outputs: Array<Record<string, unknown>>;
  evidence_checksum: string;
  data_versions: string[];
  model_versions: string[];
  connector_states: Array<Record<string, unknown>>;
  PIT_summary: Record<string, unknown>;
  performance_observation: Record<string, unknown>;
  in_sample_out_of_sample_label: string;
  warnings: Array<Record<string, unknown>>;
  source_rights: Array<Record<string, unknown>>;
}

export interface VizaPointInTimeEvidenceCheck {
  evidence_ref: string;
  status: string;
  cutoff: string;
  timestamp_available: string | null;
  message: string;
}

export interface VizaBatchCacheKey {
  node_id: string;
  graph_hash: string;
  universe_version: string | null;
  timestamp_cutoff: string;
  attribute_versions: Record<string, string>;
  source_versions: Record<string, string>;
  checksum: string;
}

export interface VizaBatchRunDiagnostics {
  row_count: number;
  relationship_count: number;
  warning_count: number;
  top_ticker: string | null;
  score_min: number | null;
  score_max: number | null;
  score_mean: number | null;
  pit_status: string;
  pit_checked_count: number;
  pit_violation_count: number;
  pit_not_applicable_count: number;
}

export interface VizaBatchRunItem {
  sequence: number;
  cutoff: string;
  methodology_id: string;
  methodology_version_id: string | null;
  label: string | null;
  run_id: string | null;
  status: string;
  graph_hash: string;
  result_checksum: string;
  warning_codes: string[];
  pit_status: string;
  pit_checks: VizaPointInTimeEvidenceCheck[];
  diagnostics: VizaBatchRunDiagnostics;
  cache_keys: VizaBatchCacheKey[];
  error: string | null;
  result: MethodologyRunResult | null;
}

export interface VizaBatchProgressEvent {
  sequence: number;
  total: number;
  cutoff: string | null;
  methodology_id: string | null;
  methodology_version_id: string | null;
  run_id: string | null;
  status: string;
  message: string;
}

export interface VizaBatchExecutionResult {
  batch_id: string;
  status: string;
  started_at: string;
  finished_at: string;
  total_runs: number;
  completed_runs: number;
  failed_runs: number;
  cancelled_runs: number;
  progress: VizaBatchProgressEvent[];
  results: VizaBatchRunItem[];
}

export interface VizaBatchMethodologyInput {
  graph: VizaMethodologyGraph;
  methodology_version_id?: string | null;
  label?: string | null;
}

export interface VizaBatchExecutionRequest {
  graph?: VizaMethodologyGraph | null;
  methodologies?: VizaBatchMethodologyInput[];
  cutoffs: string[];
  project_id?: string | null;
  persist_results?: boolean;
  ticker_subset?: string[];
  universe_name?: string | null;
  universe_version?: string | null;
}

export interface VizaRuntimeJobProgress {
  stage: string;
  current: number;
  total: number;
  message: string;
  cache_status: string;
  cache_key_count: number;
  result_ref: string | null;
}

export interface VizaRuntimeJobRecord {
  job_id: string;
  project_id: string | null;
  job_type: string;
  status: string;
  request: Record<string, unknown>;
  progress: VizaRuntimeJobProgress;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  cancel_requested: boolean;
  result_ref: string | null;
  warnings: string[];
}

export interface VizaRuntimeJobEvent {
  event_id: string;
  job_id: string;
  sequence: number;
  event_type: string;
  status: string;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface VizaRuntimeJobCreateRequest {
  job_type: "methodology_run" | "batch_execution";
  project_id?: string | null;
  methodology_version_id?: string | null;
  graph?: VizaMethodologyGraph | null;
  batch_request?: VizaBatchExecutionRequest | null;
  timestamp_cutoff?: string | null;
  source_versions?: Record<string, string>;
  connector_states?: Record<string, string>;
  strategy_profile_hash?: string | null;
  use_cache?: boolean;
  start_immediately?: boolean;
}

export interface VizaRuntimeScheduleRequest {
  radar_id?: string | null;
  methodology_id?: string | null;
  cadence: "manual" | "daily" | "weekly" | "on_app_start";
  enabled?: boolean;
  timezone?: string;
  next_run_at?: string | null;
  definition?: Record<string, unknown>;
}

export interface VizaRuntimeScheduleRecord {
  schedule_id: string;
  project_id: string;
  radar_id: string | null;
  methodology_id: string | null;
  cadence: string;
  enabled: boolean;
  timezone: string;
  next_run_at: string | null;
  definition: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface VizaSavedRadarOutputSummary {
  radar_id: string;
  project_id: string | null;
  methodology_id: string;
  version_id: string | null;
  run_id: string | null;
  timestamp_cutoff: string | null;
  result_checksum: string;
  name: string | null;
  selected_columns: string[];
  row_count: number;
  evidence_ref_count: number;
  created_at: string;
}

export interface VizaSavedRadarOutputRecord extends VizaSavedRadarOutputSummary {
  output: Record<string, unknown>;
}

export interface VizaWatchlistRecord {
  watchlist_id: string;
  project_id: string | null;
  name: string;
  tickers: string[];
  source_radar_id: string | null;
  source_run_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface VizaAlertDefinition {
  alert_type: string;
  attribute_key?: string | null;
  operator: string;
  threshold?: number | null;
  top_n?: number | null;
  relationship_type?: string | null;
  watchlist_id?: string | null;
  severity: string;
}

export interface VizaAlertRecord {
  alert_id: string;
  project_id: string | null;
  name: string;
  definition: VizaAlertDefinition;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export type VizaExportFormat = "csv" | "json" | "methodology" | "manifest";

export interface VizaExportRedaction {
  path: string;
  evidence_ref: string | null;
  policy: string;
  reason: string;
}

export interface VizaExportRequest {
  export_format: VizaExportFormat;
  result?: MethodologyRunResult | null;
  graph?: VizaMethodologyGraph | null;
  manifest?: Record<string, unknown> | null;
  selected_columns?: string[];
  include_evidence?: boolean;
  filename?: string | null;
}

export interface VizaExportResult {
  export_format: VizaExportFormat;
  content_type: string;
  filename: string;
  payload: string;
  redactions: VizaExportRedaction[];
  blocked: boolean;
}

export function isVizaNodeType(value: string): value is VizaNodeType {
  return (VIZA_NODE_TYPES as readonly string[]).includes(value);
}

export function isVizaEdgeType(value: string): value is VizaEdgeType {
  return (VIZA_EDGE_TYPES as readonly string[]).includes(value);
}
