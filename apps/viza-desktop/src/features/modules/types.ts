export interface VizaModuleRequirement {
  module_id: string;
  version_range: string;
  required: boolean;
}

export interface NodeTypeDefinition {
  type_id: string;
  display_name: string;
  category: string;
  extends: string;
  description: string | null;
  inspector_schema: Record<string, unknown>;
  allowed_incoming_edges: string[];
  allowed_outgoing_edges: string[];
  runtime_handler: string | null;
  legacy_type: string | null;
  visual: Record<string, unknown>;
}

export interface VizaModuleManifest {
  schema: "viza.module_manifest.v1";
  module_id: string;
  module_version: string;
  display_name: string;
  domain: string;
  description: string | null;
  entity_types: Record<string, unknown>;
  node_types: Record<string, NodeTypeDefinition>;
  edge_types: Record<string, unknown>;
  output_views: Record<string, unknown>;
  data_connectors: string[];
  validation_rules: string[];
  runtime_handlers: Record<string, string>;
  palette_groups: Array<{
    group_id: string;
    display_name: string;
    node_types: string[];
  }>;
}

export interface ResolvedNodeType {
  requested_type_id: string;
  status: string;
  module_id: string | null;
  module_installed: boolean;
  node_type: NodeTypeDefinition | null;
  legacy_type: string | null;
  placeholder: Record<string, unknown> | null;
  message: string | null;
}

export interface ModuleCompatibilityResult {
  module_id: string;
  required: boolean;
  version_range: string;
  installed: boolean;
  installed_version: string | null;
  status: string;
  message: string;
}
