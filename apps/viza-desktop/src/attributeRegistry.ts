import registry from "../../../config/viza_attribute_registry.json";

import type { VizaAttributeDefinition, VizaAttributeRegistry } from "./vizaGraph";

export const attributeRegistry = registry as VizaAttributeRegistry;

export const starterAttributes: VizaAttributeDefinition[] =
  attributeRegistry.attributes.map(normalizeAttributeDefinition);

export function findAttribute(key: string): VizaAttributeDefinition | undefined {
  return starterAttributes.find((attribute) => attribute.key === key);
}

function normalizeAttributeDefinition(
  attribute: VizaAttributeDefinition,
): VizaAttributeDefinition {
  const evidenceOnly =
    attribute.evidence_only ?? (attribute.contribution_stage === "evidence_only");
  const productionScoringAllowed =
    attribute.production_scoring_allowed ??
    (!evidenceOnly &&
      attribute.deprecation_status !== "deprecated" &&
      ["production", "research", "shadow"].includes(attribute.contribution_stage));

  return {
    ...attribute,
    source_type: attribute.source_type ?? "internal_aat",
    frequency: attribute.frequency ?? "unknown",
    coverage: attribute.coverage ?? "starter",
    coverage_universe: attribute.coverage_universe ?? "local_viza_starter_universes",
    freshness: attribute.freshness ?? "prototype_snapshot",
    timestamp_policy: attribute.timestamp_policy ?? "timestamp_available",
    entitlement_policy: attribute.entitlement_policy ?? "internal",
    cache_policy: attribute.cache_policy ?? "local_cache_allowed",
    production_scoring_allowed: productionScoringAllowed,
    evidence_only: evidenceOnly,
    allowed_transforms:
      attribute.allowed_transforms && attribute.allowed_transforms.length > 0
        ? attribute.allowed_transforms
        : defaultAllowedTransforms(attribute.unit),
    compatible_node_types:
      attribute.compatible_node_types && attribute.compatible_node_types.length > 0
        ? attribute.compatible_node_types
        : defaultCompatibleNodeTypes(productionScoringAllowed),
    limitations:
      attribute.limitations && attribute.limitations.length > 0
        ? attribute.limitations
        : evidenceOnly
          ? ["Evidence-only attributes require explicit user acknowledgement before scoring."]
          : [],
    owner: attribute.owner ?? "aat",
    model_version: attribute.model_version ?? "prototype_v0",
    data_version: attribute.data_version ?? "local_or_prototype_v0",
    deprecation_status: attribute.deprecation_status ?? "active",
  };
}

function defaultAllowedTransforms(unit: string): string[] {
  if (["basis_points", "score", "usd", "count"].includes(unit)) {
    return ["percentile_rank", "z_score", "absolute_value"];
  }
  if (unit === "boolean") {
    return ["boolean_threshold"];
  }
  return [];
}

function defaultCompatibleNodeTypes(productionScoringAllowed: boolean): string[] {
  const nodeTypes = ["attribute", "filter", "output_radar", "relationship"];
  return productionScoringAllowed ? [...nodeTypes, "score"] : nodeTypes;
}
