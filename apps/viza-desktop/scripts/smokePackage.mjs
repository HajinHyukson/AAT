import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import net from "node:net";
import os from "node:os";
import path from "node:path";

const appRoot = process.cwd();
const releaseDir = path.join(appRoot, "release");
const releaseRoot = path.join(appRoot, "release", "win-unpacked");
const executablePath = path.join(releaseRoot, "VIZA.exe");
const resourcesPath = path.join(releaseRoot, "resources");
const engineRoot = path.join(resourcesPath, "engine");
const sidecarPath = path.join(engineRoot, "viza-engine.exe");

assert.ok(fs.existsSync(executablePath), `Missing packaged executable: ${executablePath}`);
assert.ok(fs.existsSync(path.join(resourcesPath, "app.asar")), "Missing Electron app.asar.");
assert.ok(fs.existsSync(sidecarPath), "Missing bundled VIZA engine sidecar.");
assert.ok(fs.existsSync(path.join(engineRoot, "viza", "service.py")), "Missing VIZA engine service.");
assert.ok(
  fs.existsSync(path.join(engineRoot, "viza", "diagnostics.py")),
  "Missing VIZA engine diagnostics module.",
);
assert.ok(
  fs.existsSync(path.join(engineRoot, "viza", "equity", "runtime.py")),
  "Missing VIZA equity runtime wedge module.",
);
assert.ok(
  fs.existsSync(path.join(engineRoot, "viza", "equity", "preview.py")),
  "Missing VIZA equity packaged preview adapter.",
);
assert.ok(
  fs.existsSync(path.join(engineRoot, "config", "viza_attribute_registry.json")),
  "Missing VIZA attribute registry.",
);
assert.ok(
  fs.existsSync(path.join(engineRoot, "config", "mvp_universe.json")),
  "Missing MVP universe config.",
);
assert.ok(
  fs.existsSync(path.join(engineRoot, "config", "pilot_sp500_universe.json")),
  "Missing pilot S&P 500 universe config.",
);
assert.ok(
  fs.existsSync(path.join(engineRoot, "config", "viza_event_registry.json")),
  "Missing VIZA event registry.",
);
assert.ok(
  fs.existsSync(path.join(engineRoot, "config", "viza_insight_registry.json")),
  "Missing VIZA insight registry.",
);
assert.ok(
  fs.existsSync(path.join(engineRoot, "config", "viza_strategy_profile_templates.json")),
  "Missing VIZA strategy profile templates.",
);
assert.ok(
  fs.existsSync(path.join(engineRoot, "viza", "decisions.py")),
  "Missing VIZA decisions executor (Phase A/B/C of VIZA_OUTPUT_RADAR_DECISIONS_PLAN).",
);
assert.ok(
  fs.existsSync(path.join(engineRoot, "viza", "decisions_redaction.py")),
  "Missing VIZA decisions package-redaction module (Phase C.1).",
);
assert.ok(
  fs.existsSync(path.join(engineRoot, "viza", "decisions_backtesting.py")),
  "Missing VIZA decisions backtesting evaluator (Phase D).",
);
// Phase 26-33 backend modules. Each one must be packaged so the sidecar
// boots with the new compliance surface and the radar/argumentation paths.
assert.ok(
  fs.existsSync(path.join(engineRoot, "viza", "commands.py")),
  "Missing VIZA commands module (Phase 27).",
);
assert.ok(
  fs.existsSync(path.join(engineRoot, "viza", "feel_lite.py")),
  "Missing VIZA FEEL-Lite evaluator (Phase 27/29).",
);
assert.ok(
  fs.existsSync(path.join(engineRoot, "viza", "radar.py")),
  "Missing VIZA radar assembly module (Phase 27).",
);
assert.ok(
  fs.existsSync(path.join(engineRoot, "viza", "concepts.py")),
  "Missing VIZA SKOS concepts module (Phase 26).",
);
assert.ok(
  fs.existsSync(path.join(engineRoot, "viza", "decision_tables.py")),
  "Missing VIZA decision-tables module (Phase 29).",
);
assert.ok(
  fs.existsSync(path.join(engineRoot, "viza", "dmn_export.py")),
  "Missing VIZA DMN exporter (Phase 29).",
);
assert.ok(
  fs.existsSync(path.join(engineRoot, "viza", "fibo.py")),
  "Missing VIZA FIBO mappings module (Phase 30).",
);
assert.ok(
  fs.existsSync(path.join(engineRoot, "viza", "argumentation.py")),
  "Missing VIZA argumentation module (Phase 31).",
);
assert.ok(
  fs.existsSync(path.join(engineRoot, "viza", "event_patterns.py")),
  "Missing VIZA event-pattern module (Phase 32).",
);
assert.ok(
  fs.existsSync(path.join(engineRoot, "viza", "provenance.py")),
  "Missing VIZA PROV graph module (Phase 33).",
);
// Phase 26-33 config registries. Each one is required for the engine to
// load taxonomies and FIBO mappings; absence would surface at runtime
// with a load-time exception that smoke would otherwise miss.
assert.ok(
  fs.existsSync(path.join(engineRoot, "config", "viza_concepts.json")),
  "Missing VIZA SKOS concepts registry (Phase 26).",
);
assert.ok(
  fs.existsSync(path.join(engineRoot, "config", "viza_command_taxonomy.json")),
  "Missing VIZA command taxonomy (Phase 27).",
);
assert.ok(
  fs.existsSync(path.join(engineRoot, "config", "viza_command_conflicts.json")),
  "Missing VIZA command-conflicts registry (Phase 27/31).",
);
assert.ok(
  fs.existsSync(path.join(engineRoot, "config", "viza_command_language_gate.json")),
  "Missing VIZA command-language-gate config (Phase 27).",
);
assert.ok(
  fs.existsSync(path.join(engineRoot, "config", "viza_bkm_registry.json")),
  "Missing VIZA BKM registry (Phase 29).",
);
assert.ok(
  fs.existsSync(path.join(engineRoot, "config", "viza_fibo_mappings.json")),
  "Missing VIZA FIBO mappings (Phase 30).",
);
assert.ok(
  fs.existsSync(
    path.join(engineRoot, "config", "viza_modules", "viza.real_estate.acquisition.json"),
  ),
  "Missing VIZA real estate module manifest.",
);
assert.ok(
  fs.existsSync(
    path.join(
      engineRoot,
      "docs",
      "equity_module",
      "v0.1",
      "registries",
      "viza.finance.equity_investment.manifest.json",
    ),
  ),
  "Missing packaged equity module manifest resource.",
);
assert.ok(
  fs.existsSync(
    path.join(
      engineRoot,
      "docs",
      "equity_module",
      "v0.1",
      "fixtures",
      "first_wedge_sec_quality_value",
      "sec_fmp_fred_runtime_wedge_fixture.json",
    ),
  ),
  "Missing packaged equity SEC-first mock preview fixture.",
);
assert.ok(
  fs.readdirSync(releaseDir).some((name) => /^VIZA-.*\.exe$/i.test(name)),
  "Missing Windows installer artifact.",
);

await smokePackagedEngineApi({ equityPreviewEnabled: false, runRuntimeJob: true });
await smokePackagedEngineApi({ equityPreviewEnabled: true, runRuntimeJob: false });

console.log("VIZA Windows package contents smoke passed.");

async function smokePackagedEngineApi({ equityPreviewEnabled, runRuntimeJob }) {
  const port = await findAvailablePort();
  const token = "viza-smoke-token";
  const fmpSecret = "PACKAGED_SMOKE_FMP_SECRET_SHOULD_NOT_APPEAR";
  const fredSecret = "PACKAGED_SMOKE_FRED_SECRET_SHOULD_NOT_APPEAR";
  const projectStorePath = path.join(
    fs.mkdtempSync(path.join(os.tmpdir(), "viza-package-smoke-")),
    "viza_projects.sqlite3",
  );
  const child = spawn(sidecarPath, [], {
    cwd: engineRoot,
    env: {
      ...process.env,
      VIZA_CONFIG_DIR: path.join(engineRoot, "config"),
      VIZA_ENGINE_HOST: "127.0.0.1",
      VIZA_ENGINE_PORT: String(port),
      VIZA_ENGINE_ROOT: engineRoot,
      VIZA_ENGINE_TOKEN: token,
      VIZA_PROJECT_STORE_PATH: projectStorePath,
      VIZA_EQUITY_RUNTIME_HANDLERS_ENABLED: equityPreviewEnabled ? "true" : "false",
      VIZA_EQUITY_SEC_WEDGE_ENABLED: equityPreviewEnabled ? "true" : "false",
      VIZA_EQUITY_FMP_ENABLED: "false",
      VIZA_EQUITY_FRED_ENABLED: "false",
      VIZA_EQUITY_LIVE_INTEGRATION_TESTS: "false",
      VIZA_EQUITY_PREVIEW_PERSISTENCE_ENABLED: equityPreviewEnabled ? "true" : "false",
      VIZA_EQUITY_PREVIEW_REPLAY_REFRESH_ENABLED: "false",
      FMP_API_KEY: fmpSecret,
      FRED_API_KEY: fredSecret,
    },
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });
  let stderr = "";
  child.stdout.on("data", () => {});
  child.stderr.on("data", (chunk) => {
    stderr += chunk.toString();
  });

  try {
    await waitForHealth(port, token);
    const attributes = await requestJson(port, token, "/viza/attributes");
    const universes = await requestJson(port, token, "/viza/universes");
    const connectors = await requestJson(port, token, "/viza/connectors");
    const diagnostics = await requestJson(port, token, "/viza/diagnostics");

    assert.ok(attributes.attributes.length >= 70, "Packaged engine loaded too few attributes.");
    assert.equal(universes.length, 2, "Packaged engine should load bundled universes.");
    assert.equal(connectors.length, 9, "Packaged engine should load bundled connectors.");
    assert.equal(
      diagnostics.config_files.filter((file) => !file.exists).length,
      0,
      "Packaged diagnostics reported missing config files.",
    );

    if (equityPreviewEnabled) {
      const modules = await requestJson(port, token, "/viza/modules");
      assert.ok(
        modules.some((module) => module.module_id === "viza.finance.equity_investment"),
        "Equity module should load when the packaged preview flags are enabled.",
      );
      const status = await requestJson(port, token, "/viza/equity/runtime-wedge/status");
      assert.equal(status.enabled, true, "Equity preview status should be enabled.");
      const preview = await requestJson(port, token, "/viza/equity/runtime-wedge/preview", {
        method: "POST",
        body: JSON.stringify({
          target: { cik: "0000320193", ticker_alias: "AAPL" },
          profile_id: "quality_value_long_only",
          package_mode: "marketplace_draft",
          include_fmp: false,
          include_fred: false,
          use_live_connectors: false,
          cutoff_timestamp: null,
          mock_fixture_id: "sec_fmp_fred_runtime_wedge_fixture",
          persist_run: true,
        }),
      });
      const previewJson = JSON.stringify(preview);
      assert.equal(preview.module_id, "viza.finance.equity_investment");
      assert.equal(preview.persisted, true, "Packaged preview should persist when MVP flags are enabled.");
      assert.equal(preview.persistence_status, "persisted", "Packaged preview persistence should succeed.");
      assert.ok(preview.evidence_summary.available_at, "Preview missing PIT available_at.");
      assert.ok(preview.source_rights_report.policies.length, "Preview missing rights policies.");
      assert.ok(preview.validation_report.rules.length, "Preview missing validation rules.");
      assert.ok(preview.package_redaction_preview.redacted, "Preview missing redaction summary.");
      assert.match(preview.output_preview.non_advice_boundary, /not personalized investment advice/i);
      assert.equal(preview.audit.fixture_mode, true, "Packaged preview should use mocked fixture mode.");
      assert.equal(previewJson.includes(fmpSecret), false, "FMP key leaked into preview payload.");
      assert.equal(previewJson.includes(fredSecret), false, "FRED key leaked into preview payload.");
      const runs = await requestJson(port, token, "/viza/equity/runtime-wedge/runs");
      assert.ok(runs.total >= 1, "Persisted equity run did not appear in packaged run history.");
      const detail = await requestJson(
        port,
        token,
        `/viza/equity/runtime-wedge/runs/${encodeURIComponent(preview.run_id)}`,
      );
      assert.equal(detail.run_record.run_id, preview.run_id, "Packaged run detail mismatch.");
      assert.ok(detail.observations.length > 0, "Packaged run detail missing persisted observations.");
      const replay = await requestJson(
        port,
        token,
        `/viza/equity/runtime-wedge/runs/${encodeURIComponent(preview.run_id)}/replay`,
        {
          method: "POST",
          body: JSON.stringify({
            mode: "replay_from_stored_observations",
            package_mode: "marketplace_draft",
          }),
        },
      );
      assert.equal(
        replay.parent_run_id,
        preview.run_id,
        "Packaged stored-observation replay did not link to parent run.",
      );
      const packageDraft = await requestJson(
        port,
        token,
        `/viza/equity/runtime-wedge/runs/${encodeURIComponent(preview.run_id)}/package-draft`,
        {
          method: "POST",
          body: JSON.stringify({
            package_mode: "marketplace_draft",
            not_investment_advice_acknowledged: true,
          }),
        },
      );
      assert.ok(fs.existsSync(packageDraft.target_path), "Packaged MVP .viza draft was not written.");
      assert.equal(packageDraft.manifest.primary_mode, "marketplace_draft");
      assert.ok(packageDraft.pit_summary.observation_count > 0, "Package draft missing PIT summary.");
      assert.ok(packageDraft.rights_summary.policy_count > 0, "Package draft missing rights summary.");
      assert.match(packageDraft.non_advice_boundary, /not personalized investment advice/i);
      const packageInspection = await requestJson(port, token, "/viza/files/inspect", {
        method: "POST",
        body: JSON.stringify({ path: packageDraft.target_path }),
      });
      assert.notEqual(packageInspection.status, "invalid", "Packaged MVP .viza draft failed inspection.");
      const packageBytes = fs.readFileSync(packageDraft.target_path);
      assert.equal(packageBytes.includes(Buffer.from(fmpSecret)), false, "FMP key leaked into .viza package.");
      assert.equal(packageBytes.includes(Buffer.from(fredSecret)), false, "FRED key leaked into .viza package.");
      const packageJson = JSON.stringify({ packageDraft, packageInspection, detail, replay });
      assert.equal(packageJson.includes(fmpSecret), false, "FMP key leaked into package API payload.");
      assert.equal(packageJson.includes(fredSecret), false, "FRED key leaked into package API payload.");
    } else {
      const disabledPreview = await requestStatus(port, token, "/viza/equity/runtime-wedge/preview", {
        method: "POST",
        body: JSON.stringify({
          target: { cik: "0000320193", ticker_alias: "AAPL" },
          profile_id: "quality_value_long_only",
          package_mode: "marketplace_draft",
          include_fmp: false,
          include_fred: false,
          use_live_connectors: false,
        }),
      });
      assert.equal(disabledPreview.statusCode, 403, "Equity preview should be disabled by default.");
    }

    if (runRuntimeJob) {
      const graphPath = path.join(
        appRoot,
        "..",
        "..",
        "tests",
        "fixtures",
        "viza",
        "residual_momentum_event_radar.json",
      );
      const graph = JSON.parse(fs.readFileSync(graphPath, "utf-8"));
      const job = await requestJson(port, token, "/viza/jobs", {
        method: "POST",
        body: JSON.stringify({
          job_type: "methodology_run",
          graph,
          start_immediately: true,
          use_cache: false,
        }),
      });
      const finishedJob = await waitForJob(port, token, job.job_id);
      assert.notEqual(finishedJob.status, "pending", "Packaged runtime job stayed pending.");
      assert.notEqual(finishedJob.status, "running", "Packaged runtime job stayed running.");
      assert.equal(finishedJob.status, "completed", finishedJob.progress?.message || "Job failed.");
    }
  } finally {
    assert.equal(stderr.includes(fmpSecret), false, "FMP key leaked into packaged sidecar stderr.");
    assert.equal(stderr.includes(fredSecret), false, "FRED key leaked into packaged sidecar stderr.");
    await stopChild(child);
  }
}

async function waitForJob(port, token, jobId) {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    const job = await requestJson(port, token, `/viza/jobs/${encodeURIComponent(jobId)}`);
    if (["completed", "failed", "cancelled"].includes(job.status)) {
      return job;
    }
    await sleep(500);
  }
  throw new Error(`Timed out waiting for packaged runtime job ${jobId}.`);
}

async function waitForHealth(port, token) {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    try {
      await requestJson(port, token, "/health");
      return;
    } catch {
      await sleep(250);
    }
  }
  throw new Error("Packaged VIZA engine did not become healthy.");
}

function requestJson(port, token, pathname, options = {}) {
  const body = options.body ?? null;
  return new Promise((resolve, reject) => {
    const request = http.request(
      {
        hostname: "127.0.0.1",
        port,
        path: pathname,
        method: options.method ?? "GET",
        headers: {
          "x-viza-engine-token": token,
          ...(body ? { "content-type": "application/json" } : {}),
        },
        timeout: 5000,
      },
      (response) => {
        let text = "";
        response.setEncoding("utf8");
        response.on("data", (chunk) => {
          text += chunk;
        });
        response.on("end", () => {
          if ((response.statusCode ?? 500) >= 400) {
            reject(new Error(`${pathname} returned ${response.statusCode}: ${text}`));
            return;
          }
          resolve(text ? JSON.parse(text) : {});
        });
      },
    );
    request.on("timeout", () => request.destroy(new Error(`${pathname} timed out.`)));
    request.on("error", reject);
    if (body) {
      request.write(body);
    }
    request.end();
  });
}

function requestStatus(port, token, pathname, options = {}) {
  const body = options.body ?? null;
  return new Promise((resolve, reject) => {
    const request = http.request(
      {
        hostname: "127.0.0.1",
        port,
        path: pathname,
        method: options.method ?? "GET",
        headers: {
          "x-viza-engine-token": token,
          ...(body ? { "content-type": "application/json" } : {}),
        },
        timeout: 5000,
      },
      (response) => {
        let text = "";
        response.setEncoding("utf8");
        response.on("data", (chunk) => {
          text += chunk;
        });
        response.on("end", () => {
          resolve({ statusCode: response.statusCode ?? 500, text });
        });
      },
    );
    request.on("timeout", () => request.destroy(new Error(`${pathname} timed out.`)));
    request.on("error", reject);
    if (body) {
      request.write(body);
    }
    request.end();
  });
}

function findAvailablePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen({ host: "127.0.0.1", port: 0 }, () => {
      const address = server.address();
      if (!address || typeof address === "string") {
        server.close(() => reject(new Error("Could not allocate smoke-test port.")));
        return;
      }
      server.close(() => resolve(address.port));
    });
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function stopChild(child) {
  if (child.exitCode !== null) {
    return;
  }
  if (process.platform === "win32") {
    spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
  } else {
    child.kill("SIGTERM");
  }
  await Promise.race([
    new Promise((resolve) => child.once("exit", resolve)),
    sleep(3000).then(() => {
      if (child.exitCode === null) {
        child.kill("SIGKILL");
      }
    }),
  ]);
}
