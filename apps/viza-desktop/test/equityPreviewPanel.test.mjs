import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const appRoot = path.resolve(".");
const appSource = fs.readFileSync(path.join(appRoot, "src", "App.tsx"), "utf-8");
const clientSource = fs.readFileSync(path.join(appRoot, "src", "vizaEngineClient.ts"), "utf-8");
const styleSource = fs.readFileSync(path.join(appRoot, "src", "styles.css"), "utf-8");

function equityPanelSource() {
  const start = appSource.indexOf("function EquityRuntimePreviewPanel");
  const end = appSource.indexOf("function DiagnosticsPanel");
  assert.ok(start >= 0, "Equity preview panel was not found.");
  assert.ok(end > start, "Equity preview panel boundary was not found.");
  return appSource.slice(start, end);
}

test("equity preview panel is hidden unless the sidecar status enables it", () => {
  const panel = equityPanelSource();

  assert.match(panel, /!status\?\.enabled/);
  assert.match(panel, /return null/);
  assert.match(panel, /fetchEquityRuntimeWedgeStatus/);
});

test("equity preview panel calls the local engine bridge and renders trust surfaces", () => {
  const panel = equityPanelSource();

  assert.match(panel, /previewEquityRuntimeWedge/);
  assert.match(panel, /persist_run/);
  assert.match(panel, /Profile compatibility/);
  assert.match(panel, /Evidence summary/);
  assert.match(panel, /Validation report/);
  assert.match(panel, /Source-rights report/);
  assert.match(panel, /Package redaction preview/);
  assert.match(panel, /non_advice_boundary/);
  assert.match(clientSource, /\/viza\/equity\/runtime-wedge\/status/);
  assert.match(clientSource, /\/viza\/equity\/runtime-wedge\/preview/);
  assert.match(clientSource, /\/viza\/equity\/runtime-wedge\/runs/);
  assert.doesNotMatch(panel, /https?:\/\//);
});

test("equity preview history supports persisted run detail and replay", () => {
  const panel = equityPanelSource();

  assert.match(panel, /Recent Equity Preview Runs/);
  assert.match(panel, /fetchEquityPreviewRuns/);
  assert.match(panel, /fetchEquityPreviewRunDetail/);
  assert.match(panel, /replayEquityPreviewRun/);
  assert.match(panel, /exportEquityPreviewPackageDraft/);
  assert.match(panel, /Replay from stored observations/);
  assert.match(panel, /Replay with refresh/);
  assert.match(panel, /Prepare \.viza draft package/);
  assert.match(panel, /Package preview \/ export draft/);
  assert.match(panel, /Ticker is display\/lookup alias only/);
  assert.match(panel, /selectedRunDetail/);
  assert.match(panel, /proof_checksum/);
  assert.match(clientSource, /exportEquityPreviewPackageDraft/);
  assert.match(clientSource, /package-draft/);
});

test("equity preview panel keeps conservative wording", () => {
  const panel = equityPanelSource();

  assert.doesNotMatch(panel, /buy now/i);
  assert.doesNotMatch(panel, /sell now/i);
  assert.doesNotMatch(panel, /guaranteed alpha/i);
  assert.doesNotMatch(panel, /investment adviser/i);
  assert.doesNotMatch(panel, /personalized recommendation/i);
});

test("equity preview styles are packaged with the desktop app", () => {
  assert.match(styleSource, /\.equity-preview-panel/);
  assert.match(styleSource, /\.equity-status-pill\.pass/);
  assert.match(styleSource, /\.equity-status-pill\.warn/);
  assert.match(styleSource, /\.equity-status-pill\.block/);
  assert.match(styleSource, /\.equity-preview-history/);
  assert.match(styleSource, /\.equity-preview-actions/);
});
