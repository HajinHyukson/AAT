export interface VizaEvent {
  schema: "viza.event.v1";
  event_id: string;
  event_type: string;
  affected_entity_ids: string[];
  affected_asset_ids: string[];
  related_entity_ids: string[];
  observed_at: string;
  available_at: string;
  source: Record<string, unknown>;
  confidence: number;
  source_credibility: number | null;
  materiality: number | null;
  novelty: number | null;
  direction_hint: string | null;
  time_horizon_hint: string | null;
  risk_factors: string[];
  evidence_refs: string[];
  rights_policy: Record<string, unknown>;
  point_in_time_safe: boolean;
}

export interface EventQueryRequest {
  affected_entity_id?: string | null;
  affected_asset_id?: string | null;
  event_types?: string[];
  cutoff?: string | null;
  min_confidence?: number | null;
  limit?: number;
}

export interface EventQueryResult {
  events: VizaEvent[];
}

export interface ManualEventRequest {
  event_type: string;
  affected_entity_ids: string[];
  affected_asset_ids?: string[];
  related_entity_ids?: string[];
  observed_at: string;
  available_at: string;
  source?: Record<string, unknown>;
  confidence?: number;
  source_credibility?: number | null;
  materiality?: number | null;
  novelty?: number | null;
  direction_hint?: string | null;
  time_horizon_hint?: string | null;
  risk_factors?: string[];
  evidence_refs?: string[];
  rights_policy?: Record<string, unknown>;
  point_in_time_safe?: boolean;
}
