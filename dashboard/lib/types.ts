export type Contribution = {
  attribution_contribution_id: string;
  driver: string;
  name: string;
  contribution_bps: number;
  share_of_move: number | null;
  confidence: "High" | "Medium-High" | "Medium" | "Low-Medium" | "Low" | string;
  evidence: unknown[];
  contribution_stage: string;
  evidence_payload: Record<string, unknown> | null;
};

export type AttributionRun = {
  attribution_run_id: string;
  ticker: string;
  security_id: string;
  window_start: string;
  window_end: string;
  attribution_cutoff: string;
  observed_return_bps: number;
  unexplained_residual_bps: number;
  model_version: string;
  data_version: string;
  factor_basket_version: string;
  cadence: "daily" | "weekly" | "monthly" | string;
  narrative: string;
  contributions: Contribution[];
};

export type AttributionChartRange = "10d" | "1m" | "3m" | "6m" | "1y" | "max";

export type AttributionChartPricePoint = {
  date: string;
  adjusted_close: number;
  cumulative_return_pct: number;
};

export type AttributionChartContribution = {
  driver: string;
  name: string;
  contribution_pct: number;
  share_of_move: number | null;
};

export type AttributionChartPoint = {
  date: string;
  window_start: string;
  window_end: string;
  observed_return_pct: number;
  contributions: AttributionChartContribution[];
};

export type AttributionChartResponse = {
  ticker: string;
  range: AttributionChartRange;
  cadence: "daily" | "weekly" | "monthly" | string;
  start: string;
  end: string;
  price_points: AttributionChartPricePoint[];
  attribution_points: AttributionChartPoint[];
  driver_order: string[];
};

export type UniverseStock = {
  ticker: string;
  company_name: string;
  security_id: string;
  company_id: string;
  exchange: string;
  sector: string | null;
  industry: string | null;
  latest_run_id: string | null;
  latest_window_end: string | null;
  latest_observed_return_bps: number | null;
  latest_residual_bps: number | null;
  latest_price_change_usd: number | null;
  latest_residual_usd: number | null;
  top_driver: string | null;
  top_driver_confidence: string | null;
  contribution_count: number;
  has_evidence: boolean;
  run_status: "available" | "missing" | string;
};

export type UniverseCompanyOption = {
  ticker: string;
  company_name: string;
};

export type UniverseResponse = {
  rows: UniverseStock[];
  total: number;
  limit: number;
  offset: number;
  latest_run_date: string | null;
  company_options: UniverseCompanyOption[];
  sector_options: string[];
  industry_options: string[];
  exchange_options: string[];
};

export type ExposureUpdateDecision = {
  exposure_update_decision_id: string;
  ticker: string | null;
  company_id: string;
  exposure_name: string;
  decision: string;
  review_required: boolean;
  confidence: string;
  rationale: string;
  evidence_event_ids: string[];
  model_version: string;
  evaluated_at: string;
};
