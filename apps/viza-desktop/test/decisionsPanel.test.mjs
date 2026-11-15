import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const appRoot = path.resolve(".");
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

// The seven structural points are defended by code, not by copy alone. These
// tests check that the load-bearing strings exist in the UI source so a future
// edit cannot silently violate the simulator frame without failing CI.

test("decisions panel surfaces the sandbox replay framing", () => {
  assert.match(panelSource, /Decisions \(sandbox replay\)/);
  assert.match(panelSource, /Sandbox replay only/);
  assert.match(
    panelSource,
    /replays a\s+stored run from observations already persisted/,
  );
  assert.match(cardSource, /Sandbox replay/);
});

test("decision card surfaces non-advice disclaimer and rule provenance", () => {
  assert.match(cardSource, /Not investment advice/);
  assert.match(cardSource, /Research-process flag from a user-authored rule/);
  assert.match(cardSource, /decision\.action_template/);
  assert.match(cardSource, /decision\.rule_text/);
});

test("decisions UI never uses directive language", () => {
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

test("decisions UI surfaces PIT state and source rights state from the API", () => {
  assert.match(cardSource, /Latest triggering observation/);
  assert.match(cardSource, /Look-ahead risk/);
  assert.match(cardSource, /Source rights/);
  assert.match(cardSource, /max_observation_available_at/);
});

test("decisions UI surfaces the audit chain and evidence inspector", () => {
  assert.match(cardSource, /Show evidence chain/);
  assert.match(cardSource, /Hide evidence chain/);
  assert.match(cardSource, /trigger_observation_ids/);
  assert.match(cardSource, /audit\.run_id/);
  assert.match(cardSource, /audit\.graph_hash/);
  assert.match(cardSource, /audit\.profile_version/);
});

test("decisions client calls the engine bridge with token and replay endpoint", () => {
  assert.match(clientSource, /x-viza-engine-token/);
  assert.match(clientSource, /\/viza\/runs\//);
  assert.match(clientSource, /\/decisions\b/);
  assert.match(clientSource, /\/decisions\/replay/);
  assert.match(clientSource, /window\.vizaDesktop/);
  assert.doesNotMatch(clientSource, /https?:\/\//);
});

test("decisions UI provides a cutoff control and reload control", () => {
  assert.match(panelSource, /Replay cutoff/);
  assert.match(panelSource, /Replay at cutoff/);
  assert.match(panelSource, /Reload full history/);
});

test("decisions types mirror the Phase A schema", () => {
  assert.match(typesSource, /schema: "viza\.decision\.v1"/);
  assert.match(typesSource, /mode: VizaDecisionMode/);
  assert.match(typesSource, /VizaDecisionMode = "sandbox_replay"/);
  assert.match(typesSource, /not_investment_advice: boolean/);
});
