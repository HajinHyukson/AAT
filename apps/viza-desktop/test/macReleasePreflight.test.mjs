import assert from "node:assert/strict";
import test from "node:test";

import {
  hasNotarizationCredentials,
  hasSigningIdentity,
  verifyMacReleasePreflight,
} from "../scripts/preflightMacRelease.mjs";

test("mac release preflight accepts App Store Connect API credentials", () => {
  assert.equal(
    hasNotarizationCredentials({
      APPLE_API_KEY: "/tmp/AuthKey.p8",
      APPLE_API_KEY_ID: "KEYID12345",
      APPLE_API_ISSUER: "issuer-id",
    }),
    true,
  );
});

test("mac release preflight accepts explicit signing configuration", () => {
  assert.equal(hasSigningIdentity({ CSC_NAME: "Developer ID Application: AAT" }, "win32"), true);
  assert.equal(hasSigningIdentity({}, "win32"), false);
});

test("mac release preflight refuses non-macOS release builds", () => {
  assert.throws(
    () =>
      verifyMacReleasePreflight({
        env: {
          APPLE_API_KEY: "/tmp/AuthKey.p8",
          APPLE_API_KEY_ID: "KEYID12345",
          APPLE_API_ISSUER: "issuer-id",
          CSC_NAME: "Developer ID Application: AAT",
        },
        platform: "win32",
      }),
    /must be built on macOS/,
  );
});
