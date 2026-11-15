import assert from "node:assert/strict";
import { createRequire } from "node:module";
import path from "node:path";
import test from "node:test";

const require = createRequire(import.meta.url);
const {
  prependPythonPath,
  resolveEngineRoot,
  resolveMethodologyDirectory,
  resolveRepoRoot,
} = require("../electron/desktopPaths.cjs");

test("development engine root resolves to the repository root", () => {
  const currentDir = path.join("C:", "Users", "dev", "AAT", "apps", "viza-desktop", "electron");

  assert.equal(resolveRepoRoot(currentDir), path.join("C:", "Users", "dev", "AAT"));
  assert.equal(
    resolveEngineRoot({
      currentDir,
      isPackaged: false,
      resourcesPath: path.join("C:", "unused"),
    }),
    path.join("C:", "Users", "dev", "AAT"),
  );
});

test("packaged engine root resolves inside Electron resources", () => {
  const resourcesPath = path.join("C:", "Users", "dev", "AAT", "apps", "release", "resources");

  assert.equal(
    resolveEngineRoot({
      currentDir: path.join(resourcesPath, "app.asar", "electron"),
      isPackaged: true,
      resourcesPath,
    }),
    path.join(resourcesPath, "engine"),
  );
});

test("methodology directory is user writable documents path", () => {
  const appLike = {
    getPath(name) {
      assert.equal(name, "documents");
      return path.join("C:", "Users", "dev", "Documents");
    },
  };

  assert.equal(
    resolveMethodologyDirectory(appLike),
    path.join("C:", "Users", "dev", "Documents", "VIZA Methodologies"),
  );
});

test("python path includes packaged engine first", () => {
  const engineRoot = path.join("C:", "VIZA", "resources", "engine");
  assert.equal(prependPythonPath(engineRoot, ""), engineRoot);
  assert.equal(
    prependPythonPath(engineRoot, path.join("C:", "Python", "Lib")),
    `${engineRoot}${path.delimiter}${path.join("C:", "Python", "Lib")}`,
  );
});
