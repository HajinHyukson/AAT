export interface VizaStrategyProfile {
  schema: "viza.strategy_profile.v1";
  strategy_profile_id: string;
  display_name: string;
  domain: string;
  module_id: string;
  entity_types: string[];
  universe_constraints: Record<string, unknown>;
  holding_period: Record<string, string>;
  preferred_indicators: string[];
  catalyst_types: string[];
  required_confirmations: string[];
  risk_limits: Record<string, unknown>;
  output_preferences: Record<string, unknown>;
  action_thresholds: Record<string, number>;
  evidence_requirements: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface StrategyProfileTemplateCatalog {
  schema: "viza.strategy_profile_templates.v1";
  template_version: string;
  templates: StrategyProfileCreateRequest[];
}

export interface StrategyProfileCreateRequest {
  strategy_profile_id?: string | null;
  display_name: string;
  domain?: string;
  module_id?: string;
  entity_types?: string[];
  universe_constraints?: Record<string, unknown>;
  holding_period?: Record<string, string>;
  preferred_indicators?: string[];
  catalyst_types?: string[];
  required_confirmations?: string[];
  risk_limits?: Record<string, unknown>;
  output_preferences?: Record<string, unknown>;
  action_thresholds?: Record<string, number>;
  evidence_requirements?: Record<string, unknown>;
  template_id?: string | null;
  label?: string | null;
  message?: string | null;
}
