import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const appRoot = path.resolve(scriptDir, "..");
const repoRoot = path.resolve(appRoot, "..", "..");
const sidecarDir = path.join(appRoot, "packaging", "engine");
const sidecarBuildDir = path.join(sidecarDir, "build");
const engineEntryPath = path.join(scriptDir, "viza_engine_entry.py");
const targetPlatform = process.env.VIZA_ENGINE_TARGET_PLATFORM || process.platform;
const executableName = targetPlatform === "win32" ? "viza-engine.exe" : "viza-engine";
const sidecarPath = path.join(sidecarDir, executableName);
const pythonCommand =
  process.env.VIZA_RELEASE_PYTHON || (targetPlatform === "win32" ? "python" : "python3");

try {
  main();
} catch (error) {
  console.error("VIZA engine sidecar build failed:");
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}

function main() {
  ensurePyInstaller();
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
  if (targetPlatform !== "win32") {
    fs.chmodSync(sidecarPath, 0o755);
  }
  assertFile(sidecarPath, "Missing generated VIZA engine sidecar.");
  console.log(`VIZA engine sidecar built: ${sidecarPath}`);
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
