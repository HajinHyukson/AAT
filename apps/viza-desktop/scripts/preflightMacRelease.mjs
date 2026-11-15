import { execFileSync } from "node:child_process";
import { pathToFileURL } from "node:url";

export function hasNotarizationCredentials(env = process.env) {
  const hasApiKey = env.APPLE_API_KEY && env.APPLE_API_KEY_ID && env.APPLE_API_ISSUER;
  const hasAppleId = env.APPLE_ID && env.APPLE_APP_SPECIFIC_PASSWORD && env.APPLE_TEAM_ID;
  const hasKeychainProfile = env.APPLE_KEYCHAIN_PROFILE;
  return Boolean(hasApiKey || hasAppleId || hasKeychainProfile);
}

export function hasSigningIdentity(env = process.env, platform = process.platform) {
  if (env.CSC_LINK || env.CSC_NAME) {
    return true;
  }
  if (platform !== "darwin") {
    return false;
  }

  try {
    const output = execFileSync("security", ["find-identity", "-v", "-p", "codesigning"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    });
    return output.includes("Developer ID Application");
  } catch {
    return false;
  }
}

export function verifyMacReleasePreflight({
  env = process.env,
  platform = process.platform,
} = {}) {
  const errors = [];

  if (platform !== "darwin") {
    errors.push("macOS release artifacts must be built on macOS.");
  }
  if (!hasSigningIdentity(env, platform)) {
    errors.push(
      "Developer ID Application signing identity is missing. Install the certificate in Keychain or set CSC_LINK/CSC_NAME.",
    );
  }
  if (!hasNotarizationCredentials(env)) {
    errors.push(
      "Apple notarization credentials are missing. Prefer APPLE_API_KEY, APPLE_API_KEY_ID, and APPLE_API_ISSUER.",
    );
  }

  if (errors.length > 0) {
    throw new Error(errors.map((error) => `- ${error}`).join("\n"));
  }
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    verifyMacReleasePreflight();
    console.log("VIZA macOS release preflight passed.");
  } catch (error) {
    console.error("VIZA macOS release preflight failed:");
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  }
}
