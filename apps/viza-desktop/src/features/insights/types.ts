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

export interface InsightQueryRequest {
  entity_id?: string | null;
  asset_id?: string | null;
  insight_types?: string[];
  cutoff?: string | null;
  min_confidence?: number | null;
  limit?: number;
}

export interface InsightQueryResult {
  insights: VizaInsight[];
}
