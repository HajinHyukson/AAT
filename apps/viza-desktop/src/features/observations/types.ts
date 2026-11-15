export interface VizaObservation {
  schema: "viza.observation.v1";
  observation_id: string;
  entity_id: string;
  asset_id: string | null;
  attribute_key: string;
  value: unknown;
  unit: string | null;
  observed_at: string;
  available_at: string;
  retrieved_at: string;
  source_id: string;
  connector_id: string;
  source_record: string | null;
  data_version: string | null;
  model_version: string | null;
  confidence: number | null;
  rights_policy: Record<string, unknown>;
  checksum: string;
}

export interface ObservationQueryRequest {
  entity_id?: string | null;
  asset_id?: string | null;
  attribute_key?: string | null;
  cutoff?: string | null;
  limit?: number;
}

export interface ObservationQueryResult {
  observations: VizaObservation[];
}

export interface ObservationIngestRequest {
  observations?: Array<Record<string, unknown>>;
  entity_id?: string | null;
  asset_id?: string | null;
  ohlcv_rows?: Array<Record<string, unknown>>;
  source_id?: string;
  connector_id?: string;
  source_record?: string | null;
  data_version?: string;
  model_version?: string;
  rights_policy?: Record<string, unknown>;
}
