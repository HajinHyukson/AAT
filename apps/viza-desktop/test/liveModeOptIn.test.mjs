import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const appRoot = path.resolve(".");
const dialogSource = fs.readFileSync(
  path.join(appRoot, "src", "features", "decisions", "LiveModeOptInDialog.tsx"),
  "utf-8",
);
const panelSource = fs.readFileSync(
  path.join(appRoot, "src", "features", "decisions", "DecisionsPanel.tsx"),
  "utf-8",
);
const cardSource = fs.readFileSync(
  path.join(appRoot, "src", "features", "decisions", "DecisionCard.tsx"),
  "utf-8",
);
const clientSource = fs.readFileSync(
  path.join(appRoot, "src", "features", "decisions", "decisionsClient.ts"),
  "utf-8",
);
const typesSource = fs.readFileSync(
  path.join(appRoot, "src", "features", "decisions", "types.ts"),
  "utf-8",
);

test("live-mode opt-in dialog renders disclosure version and required acknowledgement", () => {
  assert.match(dialogSource, /Activate live mode/);
  assert.match(dialogSource, /Disclosure version/);
  assert.match(dialogSource, /status\.disclosure_text/);
  assert.match(dialogSource, /I understand this is not investment advice/);
  assert.match(dialogSource, /recordLiveModeOptIn/);
  assert.match(dialogSource, /accepted_disclosure_version: status\.disclosure_version/);
});

test("live-mode opt-in dialog disables acceptance until acknowledgement is checked", () => {
  assert.match(dialogSource, /acknowledged.*checkbox/s);
  assert.match(dialogSource, /disabled=\{!acknowledged \|\| submitting\}/);
});

test("decisions panel surfaces a sandbox vs live mode selector", () => {
  assert.match(panelSource, /role="radiogroup"/);
  assert.match(panelSource, /Sandbox replay/);
  assert.match(panelSource, /Live mode/);
  assert.match(panelSource, /value="sandbox_replay"/);
  assert.match(panelSource, /value="live"/);
});

test("decisions panel shows live-mode badge and engine-flag warning", () => {
  assert.match(panelSource, /Live mode/);
  assert.match(panelSource, /decisions-panel-badge-live/);
  assert.match(panelSource, /Live mode is not enabled in this engine/);
  // The env var name is surfaced via the API at runtime (liveStatus.env_var)
  // rather than hardcoded so the engine and UI stay in sync. Assert the
  // runtime field reference instead of the literal env name.
  assert.match(panelSource, /liveStatus\.env_var/);
});

test("decision card adapts badge text and class to decision.mode", () => {
  assert.match(cardSource, /decision\.mode === "live"/);
  assert.match(cardSource, /badgeLabel = isLive \? "Live" : "Sandbox replay"/);
  assert.match(cardSource, /decision-card-badge-live/);
});

test("decisions client exposes live-mode endpoints with engine token", () => {
  assert.match(clientSource, /\/viza\/runtime\/live-mode-status/);
  assert.match(clientSource, /\/viza\/profiles\/.+\/live-mode-opt-in/);
  assert.match(clientSource, /\/viza\/profiles\/.+\/decisions\/live/);
  assert.match(clientSource, /fetchLiveModeStatus/);
  assert.match(clientSource, /recordLiveModeOptIn/);
  assert.match(clientSource, /compileLiveDecisions/);
  // Token gate is shared with sandbox endpoints via the same client.
  assert.match(clientSource, /x-viza-engine-token/);
});

test("live-mode types mirror the engine schema", () => {
  assert.match(typesSource, /VizaDecisionMode = "sandbox_replay" \| "live"/);
  assert.match(typesSource, /VizaLiveModeOptIn/);
  assert.match(typesSource, /accepted_disclosure_version: string/);
  assert.match(typesSource, /VizaLiveDecisionsResponse/);
  assert.match(typesSource, /mode: "live"/);
});

test("live-mode UI never uses directive investment language", () => {
  // The same forbidden-language guard from the original panel test applies
  // to the new live-mode surface. Keep the regex set in sync with
  // decisionsPanel.test.mjs.
  const forbiddenLanguage = [
    /\bBuy\b/,
    /\bSell\b/,
    /\bAct now\b/i,
    /\bTrade\b/,
    /\bRecommend(ation)?\b/i,
    /\btoday\b/i,
    /\bcurrent (price|reading|market)/i,
  ];
  for (const pattern of forbiddenLanguage) {
    assert.doesNotMatch(
      dialogSource,
      pattern,
      `Dialog must not use directive language ${pattern}`,
    );
    assert.doesNotMatch(
      panelSource,
      pattern,
      `Panel must not use directive language ${pattern}`,
    );
    assert.doesNotMatch(
      cardSource,
      pattern,
      `Card must not use directive language ${pattern}`,
    );
  }
});

test("live-mode help text preserves the non-advice boundary", () => {
  // Help text for the live tab is the load-bearing line for the simulator
  // frame in live mode; assert the exact non-advice anchor.
  assert.match(panelSource, /This is not investment advice\./);
  // Live help text describes what the engine does without using "today" /
  // "current" / "recommend" — the non-advice guard is enforced above.
  assert.match(
    panelSource,
    /the latest observations the engine pulled from the local project store/,
  );
});

test("DecisionsPanel is wired into App.tsx and rendered with run_id", () => {
  const appSource = fs.readFileSync(path.join(appRoot, "src", "App.tsx"), "utf-8");
  assert.match(
    appSource,
    /import\s*\{\s*DecisionsPanel\s*\}\s*from\s+"\.\/features\/decisions\/DecisionsPanel"/,
  );
  assert.match(
    appSource,
    /<DecisionsPanel\s+runId=\{result\?\.run_id\s*\?\?\s*null\}\s*\/>/,
  );
});

test("structured live-mode error code is plumbed from client to panel", () => {
  // The client throws VizaLiveModeError with a code; the panel branches on
  // the structured code rather than substring-matching the message.
  assert.match(clientSource, /class VizaLiveModeError extends Error/);
  assert.match(clientSource, /readonly code: string/);
  assert.match(clientSource, /new VizaLiveModeError\(detailObject\.code/);
  assert.match(panelSource, /issue instanceof VizaLiveModeError/);
  assert.match(panelSource, /case "LiveModeOptInRequiredError"/);
  assert.match(panelSource, /case "LiveModeOptInStaleError"/);
  assert.match(panelSource, /case "LiveModeDisabledError"/);
  assert.match(panelSource, /case "LiveModeRuleEffectiveDateRequiredError"/);
});
