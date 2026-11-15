const FEATURE_FLAG_DEFAULTS: Record<string, boolean> = {
  VIZA_ENABLE_UNIVERSAL_CONTAINER: true,
  VIZA_ENABLE_MODULE_REGISTRY: true,
  VIZA_ENABLE_EXPERIMENTAL_GRAPH_V1: false,
  VIZA_ENABLE_NON_FINANCE_MODULES: false,
};

const TRUTHY = new Set(["1", "true", "t", "yes", "y", "on", "enabled"]);
const FALSY = new Set(["0", "false", "f", "no", "n", "off", "disabled"]);

export function featureEnabled(name: string, defaultValue = false): boolean {
  const flagName = normalizeFeatureFlagName(name);
  if (!flagName) {
    return defaultValue;
  }
  const fallback = FEATURE_FLAG_DEFAULTS[flagName] ?? defaultValue;
  const env = import.meta.env as Record<string, string | boolean | undefined>;
  const rawValue = env[flagName] ?? env[`VITE_${flagName}`];
  return parseFeatureFlagValue(rawValue, fallback);
}

export function normalizeFeatureFlagName(name: string): string {
  const normalized = String(name || "")
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  if (!normalized) {
    return "";
  }
  return normalized.startsWith("VIZA_ENABLE_") ? normalized : `VIZA_ENABLE_${normalized}`;
}

export function parseFeatureFlagValue(
  value: string | boolean | undefined,
  fallback: boolean,
): boolean {
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value !== "string") {
    return fallback;
  }

  const normalized = value.trim().toLowerCase();
  if (TRUTHY.has(normalized)) {
    return true;
  }
  if (FALSY.has(normalized)) {
    return false;
  }
  return fallback;
}
