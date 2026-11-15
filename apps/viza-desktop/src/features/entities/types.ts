export interface VizaEntity {
  schema: "viza.entity.v1";
  entity_id: string;
  entity_type: string;
  display_name: string;
  domain: string;
  module_id: string | null;
  aliases: string[];
  identifiers: Record<string, string>;
  metadata: Record<string, unknown>;
  source_lineage: Array<Record<string, unknown>>;
  rights_policy: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface VizaAsset {
  schema: "viza.asset.v1";
  entity_id: string;
  asset_id: string;
  asset_class: string;
  primary_symbol: string;
  current_name: string;
  exchange: string | null;
  country: string;
  currency: string;
  identifiers: Record<string, string>;
  sector: string | null;
  industry: string | null;
  listing_status: string;
  provider_identifier_map: Record<string, string>;
  source_lineage: Array<Record<string, unknown>>;
  created_at: string;
  updated_at: string;
}

export interface EntityResolveResult {
  query: Record<string, string>;
  entity: VizaEntity | null;
  warnings: string[];
}

export interface AssetResolveResult {
  query: Record<string, string>;
  asset: VizaAsset | null;
  warnings: string[];
}
