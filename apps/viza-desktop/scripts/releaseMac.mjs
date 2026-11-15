import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { verifyMacReleasePreflight } from "./preflightMacRelease.mjs";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const appRoot = path.resolve(scriptDir, "..");
const repoRoot = path.resolve(appRoot, "..", "..");
const sidecarDir = path.join(appRoot, "packaging", "engine");
const sidecarPath = path.join(sidecarDir, "viza-engine");
const sidecarBuildDir = path.join(sidecarDir, "build");
const engineEntryPath = path.join(scriptDir, "viza_engine_entry.py");
const releaseArch = resolveReleaseArch();
const pythonCommand = process.env.VIZA_RELEASE_PYTHON || "python3";

try {
  main();
} catch (error) {
  console.error("VIZA macOS release failed:");
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}

function main() {
  verifyMacReleasePreflight();
  ensurePyInstaller();
  run("npm", ["run", "build"], { cwd: appRoot });
  buildEngineSidecar();
  run(
    "npx",
    [
      "electron-builder",
      "--mac",
      "dmg",
      "zip",
      `--${releaseArch}`,
      "--publish",
      "never",
      "--config",
      "electron-builder.mac-release.yml",
    ],
    { cwd: appRoot },
  );
  run("npm", ["run", "smoke:package:mac"], { cwd: appRoot });
}

function resolveReleaseArch() {
  const requested = process.env.VIZA_MAC_ARCH || process.arch;
  if (requested === "arm64" || requested === "x64") {
    return requested;
  }
  throw new Error(`Unsupported VIZA_MAC_ARCH '${requested}'. Use arm64 or x64.`);
}

function ensurePyInstaller() {
  const result = spawnSync(pythonCommand, ["-c", "import PyInstaller"], {
    cwd: repoRoot,
    encoding: "utf8",
    stdio: "pipe",
  });
  if (result.status === 0) {
    return;
  }

  throw new Error(
    [
      "PyInstaller is required for the bundled VIZA engine sidecar.",
      `Install it with: ${pythonCommand} -m pip install -e ".[release]"`,
      result.stderr.trim(),
    ]
      .filter(Boolean)
      .join("\n"),
  );
}

function buildEngineSidecar() {
  fs.mkdirSync(sidecarDir, { recursive: true });
  removeGenerated(sidecarPath);
  removeGenerated(sidecarBuildDir);

  run(
    pythonCommand,
    [
      "-m",
      "PyInstaller",
      "--clean",
      "--onefile",
      "--name",
      "viza-engine",
      "--paths",
      repoRoot,
      "--distpath",
      sidecarDir,
      "--workpath",
      sidecarBuildDir,
      "--specpath",
      sidecarBuildDir,
      "--collect-submodules",
      "uvicorn",
      engineEntryPath,
    ],
    { cwd: repoRoot },
  );

  fs.chmodSync(sidecarPath, 0o755);
  assertFile(sidecarPath, "Missing generated VIZA engine sidecar.");
}

function removeGenerated(targetPath) {
  const resolvedTarget = path.resolve(targetPath);
  const resolvedSidecarDir = path.resolve(sidecarDir);
  if (
    resolvedTarget !== path.resolve(sidecarPath) &&
    !resolvedTarget.startsWith(`${resolvedSidecarDir}${path.sep}`)
  ) {
    throw new Error(`Refusing to remove path outside packaging engine dir: ${targetPath}`);
  }
  fs.rmSync(resolvedTarget, { force: true, recursive: true });
}

function assertFile(filePath, message) {
  if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
    throw new Error(`${message} ${filePath}`);
  }
}

function run(command, args, options = {}) {
  console.log(`\n$ ${[command, ...args].join(" ")}`);
  const result = spawnSync(command, args, {
    stdio: "inherit",
    ...options,
  });

  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(" ")} failed with exit code ${result.status}.`);
  }
}
