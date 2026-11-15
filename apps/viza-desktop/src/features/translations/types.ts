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

export interface TranslationRequest {
  insight_id?: string | null;
  insight?: Record<string, unknown> | null;
  strategy_profile_id?: string | null;
  strategy_profile?: Record<string, unknown> | null;
  persist?: boolean;
}
