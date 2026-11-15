import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import net from "node:net";
import os from "node:os";
import path from "node:path";

const appRoot = process.cwd();
const releaseRoot = path.join(appRoot, "release");

assert.ok(fs.existsSync(releaseRoot), `Missing release directory: ${releaseRoot}`);

const releasePaths = walk(releaseRoot);
const appBundles = releasePaths.filter(
  (candidate) => candidate.endsWith(".app") && path.basename(candidate) === "VIZA.app",
);
const dmgFiles = releasePaths.filter((candidate) => candidate.endsWith(".dmg"));
const zipFiles = releasePaths.filter((candidate) => candidate.endsWith(".zip"));

assert.ok(appBundles.length > 0, "Missing packaged VIZA.app bundle.");
assert.ok(dmgFiles.length > 0, "Missing VIZA macOS DMG artifact.");
assert.ok(zipFiles.length > 0, "Missing VIZA macOS ZIP artifact.");

for (const appBundle of appBundles) {
  const resourcesPath = path.join(appBundle, "Contents", "Resources");
  const engineRoot = path.join(resourcesPath, "engine");
  const sidecarPath = path.join(engineRoot, "viza-engine");

  assertFile(path.join(resourcesPath, "app.asar"), "Missing Electron app.asar.");
  assertFile(sidecarPath, "Missing bundled VIZA engine sidecar.");
  assertFile(path.join(engineRoot, "viza", "service.py"), "Missing VIZA engine service.");
  assertFile(
    path.join(engineRoot, "viza", "diagnostics.py"),
    "Missing VIZA engine diagnostics module.",
  );
  assertFile(
    path.join(engineRoot, "config", "viza_attribute_registry.json"),
    "Missing VIZA attribute registry.",
  );
  assertFile(path.join(engineRoot, "config", "mvp_universe.json"), "Missing MVP universe config.");
  assertFile(
    path.join(engineRoot, "config", "pilot_sp500_universe.json"),
    "Missing pilot S&P 500 universe config.",
  );
  assertFile(
    path.join(engineRoot, "config", "viza_event_registry.json"),
    "Missing VIZA event registry.",
  );
  assertFile(
    path.join(engineRoot, "config", "viza_insight_registry.json"),
    "Missing VIZA insight registry.",
  );
  assertFile(
    path.join(engineRoot, "config", "viza_strategy_profile_templates.json"),
    "Missing VIZA strategy profile templates.",
  );
  assertFile(
    path.join(engineRoot, "config", "viza_modules", "viza.real_estate.acquisition.json"),
    "Missing VIZA real estate module manifest.",
  );

  if (process.platform === "darwin") {
    await smokePackagedEngineApi(engineRoot, sidecarPath);
    run("codesign", ["--verify", "--deep", "--strict", "--verbose=2", appBundle]);
    run("codesign", ["--verify", "--strict", "--verbose=2", sidecarPath]);
    run("xcrun", ["stapler", "validate", appBundle]);
    run("spctl", ["--assess", "--type", "execute", "--verbose=4", appBundle]);
  }
}

for (const artifactPath of [...dmgFiles, ...zipFiles]) {
  assert.ok(fs.statSync(artifactPath).size > 0, `Artifact is empty: ${artifactPath}`);
}

console.log("VIZA macOS package smoke passed.");

async function smokePackagedEngineApi(engineRoot, sidecarPath) {
  const port = await findAvailablePort();
  const token = "viza-smoke-token";
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
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  child.stdout.on("data", () => {});

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
    assert.equal(finishedJob.status, "completed", finishedJob.progress?.message || "Job failed.");
  } finally {
    await stopChild(child);
  }
}

function walk(root) {
  const results = [];
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    const entryPath = path.join(root, entry.name);
    if (entry.isDirectory()) {
      results.push(entryPath);
      if (!entry.name.endsWith(".app")) {
        results.push(...walk(entryPath));
      }
    } else {
      results.push(entryPath);
    }
  }
  return results;
}

function assertFile(filePath, message) {
  assert.ok(fs.existsSync(filePath) && fs.statSync(filePath).isFile(), `${message} ${filePath}`);
}

function run(command, args) {
  execFileSync(command, args, { stdio: "inherit" });
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
