import { pathToFileURL } from "node:url";

export function hasWindowsSigningConfig(env = process.env) {
  return Boolean(
    (env.CSC_LINK || env.WIN_CSC_LINK || env.CSC_NAME) &&
      (env.CSC_KEY_PASSWORD || env.WIN_CSC_KEY_PASSWORD || env.CSC_NAME),
  );
}

export function verifyWindowsReleasePreflight({
  env = process.env,
  platform = process.platform,
} = {}) {
  const errors = [];
  const warnings = [];

  if (platform !== "win32" && env.VIZA_ALLOW_CROSS_PLATFORM_WIN_PACKAGE !== "1") {
    errors.push("Windows release artifacts should be built on Windows.");
  }
  if (env.VIZA_REQUIRE_WINDOWS_SIGNING === "1" && !hasWindowsSigningConfig(env)) {
    errors.push(
      "Windows signing configuration is missing. Set CSC_LINK/CSC_KEY_PASSWORD or CSC_NAME.",
    );
  }
  if (!hasWindowsSigningConfig(env)) {
    warnings.push("Windows package will be unsigned unless signing credentials are supplied.");
  }

  if (errors.length > 0) {
    throw new Error(errors.map((error) => `- ${error}`).join("\n"));
  }
  return { warnings };
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    const result = verifyWindowsReleasePreflight();
    for (const warning of result.warnings) {
      console.warn(`VIZA Windows release preflight warning: ${warning}`);
    }
    console.log("VIZA Windows release preflight passed.");
  } catch (error) {
    console.error("VIZA Windows release preflight failed:");
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  }
}
