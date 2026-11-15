const path = require("node:path");

function resolveRepoRoot(currentDir) {
  return path.resolve(currentDir, "..", "..", "..");
}

function resolveEngineRoot({ currentDir, isPackaged, resourcesPath }) {
  if (isPackaged) {
    return path.join(resourcesPath, "engine");
  }
  return resolveRepoRoot(currentDir);
}

function resolveMethodologyDirectory(appLike) {
  return path.join(appLike.getPath("documents"), "VIZA Methodologies");
}

function prependPythonPath(engineRoot, currentPythonPath = "") {
  return currentPythonPath ? `${engineRoot}${path.delimiter}${currentPythonPath}` : engineRoot;
}

module.exports = {
  prependPythonPath,
  resolveEngineRoot,
  resolveMethodologyDirectory,
  resolveRepoRoot,
};
