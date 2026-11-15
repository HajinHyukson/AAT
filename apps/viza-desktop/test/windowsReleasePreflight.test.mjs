import assert from "node:assert/strict";
import test from "node:test";

import {
  hasWindowsSigningConfig,
  verifyWindowsReleasePreflight,
} from "../scripts/preflightWindowsRelease.mjs";

test("windows release preflight allows unsigned local package by default", () => {
  const result = verifyWindowsReleasePreflight({
    env: {},
    platform: "win32",
  });

  assert.match(result.warnings[0], /unsigned/);
});

test("windows release preflight accepts explicit signing configuration", () => {
  assert.equal(
    hasWindowsSigningConfig({
      CSC_LINK: "C:/certs/viza.pfx",
      CSC_KEY_PASSWORD: "password",
    }),
    true,
  );
});

test("windows release preflight can require signing credentials", () => {
  assert.throws(
    () =>
      verifyWindowsReleasePreflight({
        env: { VIZA_REQUIRE_WINDOWS_SIGNING: "1" },
        platform: "win32",
      }),
    /signing configuration is missing/,
  );
});
