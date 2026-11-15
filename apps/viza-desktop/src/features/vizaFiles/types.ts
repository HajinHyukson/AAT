import type { VizaMethodologyGraph } from "../../vizaGraph";

export interface VizaFileInspectionResult {
  path: string;
  file_id: string | null;
  status: string;
  manifest: Record<string, unknown>;
  manifest_checksum: string | null;
  container_checksum: string | null;
  section_statuses: Record<string, string>;
  entries: string[];
  warnings: string[];
  errors: string[];
  visualization: VizaFileVisualization | null;
}

export interface VizaFileValidationResult {
  valid: boolean;
  inspection: VizaFileInspectionResult;
}

export interface VizaFileWriteResult {
  path: string;
  file_id: string;
  manifest_checksum: string;
  container_checksum: string;
  section_checksums: Record<string, string>;
  warnings: string[];
}

export interface VizaFileExportRequest {
  target_path: string;
  graph?: VizaMethodologyGraph | null;
  project_id?: string | null;
  methodology_version_id?: string | null;
  run_id?: string | null;
  display_name?: string | null;
  purpose?: "collaboration" | "marketplace_draft" | string;
  visibility?: "white_box" | "gray_box" | "black_box" | "output_only" | "preview_only";
  include_sections?: string[];
  include_validation_proof?: boolean;
  include_signal_outputs?: boolean;
  include_sample_outputs?: boolean;
  redact_parameters?: boolean;
  lock_sections?: string[];
  creator_id?: string | null;
  creator_display_name?: string | null;
  source_rights?: Record<string, unknown>[];
  not_investment_advice_acknowledged?: boolean;
}

export interface VizaFileExportResponse {
  result: VizaFileWriteResult;
  manifest: Record<string, unknown>;
  export_record: Record<string, unknown> | null;
}

export interface VizaFileImportRequest {
  path: string;
  project_id?: string | null;
  mode?: "open_without_import" | "import_to_project" | "fork_as_new_methodology" | "quarantine";
  save_methodology_version?: boolean;
  label?: string | null;
  message?: string | null;
}

export interface VizaFileImportResponse {
  status: string;
  source_path: string;
  manifest: Record<string, unknown>;
  graph: VizaMethodologyGraph | null;
  import_record: Record<string, unknown> | null;
  methodology_version: Record<string, unknown> | null;
  warnings: string[];
}

export interface VizaFileRecordResponse {
  file_id: string;
  imports: Record<string, unknown>[];
  exports: Record<string, unknown>[];
}

export interface VizaFileSectionsResponse {
  file_id: string;
  sections: Record<string, unknown>;
}

export interface VizaFileQuarantineResponse {
  file_id: string;
  quarantine_status: string;
  records_updated: number;
}

export interface VizaSectionVisualization {
  section_name: string;
  status: string;
  path: string | null;
  schema: string | null;
  checksum: string | null;
  reason: string | null;
  readable: boolean;
  included_in_container: boolean;
}

export interface VizaModuleCompatibilityStatus {
  module_id: string;
  required: boolean;
  version_range: string;
  installed: boolean;
  installed_version: string | null;
  status: string;
  message: string;
}

export interface VizaCompatibilitySummary {
  schema_status: string;
  checksum_status: string;
  missing_modules: string[];
  missing_connectors: string[];
  required_connectors: string[];
  permissions: Record<string, unknown>;
}

export interface VizaFileWarning {
  code: string;
  message: string;
  severity: string;
}

export interface VizaFileVisualization {
  file_id: string;
  display_name: string | null;
  object_kind: string;
  visibility: string;
  schema: string;
  required_modules: VizaModuleCompatibilityStatus[];
  contents_map: Record<string, VizaSectionVisualization>;
  compatibility: VizaCompatibilitySummary;
  available_actions: string[];
  warnings: VizaFileWarning[];
  creator: Record<string, unknown>;
  compliance_warnings: VizaFileWarning[];
  readiness_checklist: Record<string, unknown>;
  marketplace: Record<string, unknown>;
}
