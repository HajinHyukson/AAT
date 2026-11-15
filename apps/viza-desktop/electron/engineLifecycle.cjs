const crypto = require("node:crypto");
const fs = require("node:fs");
const net = require("node:net");
const path = require("node:path");

function createEngineToken() {
  return crypto.randomBytes(24).toString("hex");
}

function parseEnginePort(value, fallback = 8765) {
  const port = Number(value);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    return fallback;
  }
  return port;
}

function resolveEngineBaseUrl(host, port) {
  return `http://${host}:${port}`;
}

function resolveEngineEnvironment({
  currentEnv = process.env,
  engineRoot,
  host,
  port,
  token,
} = {}) {
  return {
    ...currentEnv,
    VIZA_CONFIG_DIR: path.join(engineRoot, "config"),
    VIZA_ENGINE_HOST: host,
    VIZA_ENGINE_PORT: String(port),
    VIZA_ENGINE_ROOT: engineRoot,
    VIZA_ENGINE_TOKEN: token,
  };
}

function resolveEngineCommand({
  engineRoot,
  platform = process.platform,
  pythonOverride = "",
  existsSync = fs.existsSync,
} = {}) {
  const executableName = platform === "win32" ? "viza-engine.exe" : "viza-engine";
  const bundledCandidates = [
    path.join(engineRoot, executableName),
    path.join(engineRoot, "bin", executableName),
  ];
  const bundledCommand = bundledCandidates.find((candidate) => existsSync(candidate));
  if (bundledCommand) {
    return {
      command: bundledCommand,
      args: [],
      usesBundledRuntime: true,
    };
  }

  return {
    command: pythonOverride || "python",
    args: ["-m", "viza.service"],
    usesBundledRuntime: false,
  };
}

async function findAvailablePort({ host = "127.0.0.1", preferredPort = 8765 } = {}) {
  if (await canListen(host, preferredPort)) {
    return preferredPort;
  }
  return listenOnEphemeralPort(host);
}

function canListen(host, port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.unref();
    server.once("error", () => resolve(false));
    server.listen({ host, port }, () => {
      server.close(() => resolve(true));
    });
  });
}

function listenOnEphemeralPort(host) {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.once("error", reject);
    server.listen({ host, port: 0 }, () => {
      const address = server.address();
      if (!address || typeof address === "string") {
        server.close(() => reject(new Error("Could not allocate a local engine port.")));
        return;
      }
      const port = address.port;
      server.close(() => resolve(port));
    });
  });
}

module.exports = {
  createEngineToken,
  findAvailablePort,
  parseEnginePort,
  resolveEngineBaseUrl,
  resolveEngineCommand,
  resolveEngineEnvironment,
};
