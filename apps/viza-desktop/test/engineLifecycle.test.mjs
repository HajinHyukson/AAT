import assert from "node:assert/strict";
import { createRequire } from "node:module";
import net from "node:net";
import path from "node:path";
import test from "node:test";

const require = createRequire(import.meta.url);
const {
  createEngineToken,
  findAvailablePort,
  parseEnginePort,
  resolveEngineBaseUrl,
  resolveEngineCommand,
  resolveEngineEnvironment,
} = require("../electron/engineLifecycle.cjs");

test("engine token is generated per local session", () => {
  const first = createEngineToken();
  const second = createEngineToken();

  assert.equal(first.length, 48);
  assert.equal(second.length, 48);
  assert.notEqual(first, second);
});

test("engine port parser keeps invalid values away from spawn env", () => {
  assert.equal(parseEnginePort("9001"), 9001);
  assert.equal(parseEnginePort("not-a-port", 8765), 8765);
  assert.equal(parseEnginePort("70000", 8765), 8765);
});

test("engine base url is derived from host and allocated port", () => {
  assert.equal(resolveEngineBaseUrl("127.0.0.1", 8765), "http://127.0.0.1:8765");
});

test("engine environment includes explicit packaged config paths", () => {
  const engineRoot = path.join("C:", "VIZA", "resources", "engine");
  const env = resolveEngineEnvironment({
    currentEnv: { EXISTING: "1" },
    engineRoot,
    host: "127.0.0.1",
    port: 8765,
    token: "secret-token",
  });

  assert.equal(env.EXISTING, "1");
  assert.equal(env.VIZA_ENGINE_ROOT, engineRoot);
  assert.equal(env.VIZA_CONFIG_DIR, path.join(engineRoot, "config"));
  assert.equal(env.VIZA_ENGINE_HOST, "127.0.0.1");
  assert.equal(env.VIZA_ENGINE_PORT, "8765");
  assert.equal(env.VIZA_ENGINE_TOKEN, "secret-token");
});

test("bundled engine command is preferred when sidecar exists", () => {
  const command = resolveEngineCommand({
    engineRoot: path.join("C:", "VIZA", "resources", "engine"),
    platform: "win32",
    existsSync: (candidate) => candidate.endsWith("viza-engine.exe"),
  });

  assert.equal(command.usesBundledRuntime, true);
  assert.equal(command.args.length, 0);
  assert.match(command.command, /viza-engine\.exe$/);
});

test("macOS bundled engine command uses the unix sidecar name", () => {
  const command = resolveEngineCommand({
    engineRoot: path.join("/", "Applications", "VIZA.app", "Contents", "Resources", "engine"),
    platform: "darwin",
    existsSync: (candidate) => candidate.endsWith("viza-engine"),
  });

  assert.equal(command.usesBundledRuntime, true);
  assert.equal(command.args.length, 0);
  assert.match(command.command, /viza-engine$/);
});

test("system python remains the development fallback", () => {
  const command = resolveEngineCommand({
    engineRoot: path.join("C:", "AAT"),
    platform: "win32",
    pythonOverride: "py -3.12",
    existsSync: () => false,
  });

  assert.equal(command.usesBundledRuntime, false);
  assert.equal(command.command, "py -3.12");
  assert.deepEqual(command.args, ["-m", "viza.service"]);
});

test("available port allocation falls back when preferred port is occupied", async () => {
  const occupiedServer = net.createServer();
  await new Promise((resolve, reject) => {
    occupiedServer.once("error", reject);
    occupiedServer.listen({ host: "127.0.0.1", port: 0 }, resolve);
  });

  try {
    const address = occupiedServer.address();
    assert.ok(address && typeof address !== "string");
    const allocatedPort = await findAvailablePort({
      host: "127.0.0.1",
      preferredPort: address.port,
    });

    assert.notEqual(allocatedPort, address.port);
    assert.ok(allocatedPort > 0);
  } finally {
    await new Promise((resolve) => occupiedServer.close(resolve));
  }
});
