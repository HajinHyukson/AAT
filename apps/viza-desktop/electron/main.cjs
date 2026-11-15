const { spawn } = require("node:child_process");
const { app, BrowserWindow, dialog, ipcMain } = require("electron");
const fsSync = require("node:fs");
const fs = require("node:fs/promises");
const http = require("node:http");
const path = require("node:path");

const {
  prependPythonPath,
  resolveEngineRoot,
  resolveMethodologyDirectory,
} = require("./desktopPaths.cjs");
const {
  createEngineToken,
  findAvailablePort,
  parseEnginePort,
  resolveEngineBaseUrl,
  resolveEngineCommand,
  resolveEngineEnvironment,
} = require("./engineLifecycle.cjs");

let mainWindow = null;
let engineProcess = null;
let engineBaseUrl = process.env.VIZA_ENGINE_URL || "http://127.0.0.1:8765";
let engineLaunchError = "";
let engineLogPath = "";
let engineRuntimeMode = "not_started";
let engineToken = "";

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1100,
    minHeight: 720,
    title: "VIZA",
    backgroundColor: "#f6f7f9",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, "preload.cjs"),
    },
  });

  const devServerUrl = process.env.VITE_DEV_SERVER_URL;
  if (devServerUrl) {
    mainWindow.loadURL(devServerUrl);
    return;
  }

  mainWindow.loadFile(path.join(__dirname, "..", "dist", "index.html"));
}

app.whenReady().then(() => {
  void ensureMethodologyDirectory();
  void startEngineService().finally(() => {
    createWindow();
  });

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  stopEngineService();
});

ipcMain.handle("viza:saveGraph", async (_event, graph) => {
  const window = BrowserWindow.getFocusedWindow() ?? mainWindow;
  const methodologyDirectory = await ensureMethodologyDirectory();
  const defaultName = `${slugify(graph.name || "untitled-methodology")}.viza.json`;
  const result = await dialog.showSaveDialog(window, {
    title: "Save VIZA Methodology",
    defaultPath: path.join(methodologyDirectory, defaultName),
    filters: [
      { name: "VIZA Methodology", extensions: ["json"] },
      { name: "JSON", extensions: ["json"] },
    ],
  });

  if (result.canceled || !result.filePath) {
    return { canceled: true };
  }

  await fs.writeFile(result.filePath, JSON.stringify(graph, null, 2) + "\n", "utf-8");
  return { canceled: false, path: result.filePath };
});

ipcMain.handle("viza:openGraph", async () => {
  const window = BrowserWindow.getFocusedWindow() ?? mainWindow;
  const result = await dialog.showOpenDialog(window, {
    title: "Open VIZA Methodology",
    properties: ["openFile"],
    filters: [
      { name: "VIZA Methodology", extensions: ["json"] },
      { name: "JSON", extensions: ["json"] },
    ],
  });

  if (result.canceled || result.filePaths.length === 0) {
    return { canceled: true };
  }

  const filePath = result.filePaths[0];
  const text = await fs.readFile(filePath, "utf-8");
  return {
    canceled: false,
    path: filePath,
    graph: JSON.parse(text),
  };
});

ipcMain.handle("viza:selectVizaFile", async () => {
  const window = BrowserWindow.getFocusedWindow() ?? mainWindow;
  const result = await dialog.showOpenDialog(window, {
    title: "Open VIZA File",
    properties: ["openFile"],
    filters: [
      { name: "VIZA Files", extensions: ["viza", "json"] },
      { name: "All Files", extensions: ["*"] },
    ],
  });

  if (result.canceled || result.filePaths.length === 0) {
    return { canceled: true };
  }

  return { canceled: false, path: result.filePaths[0] };
});

ipcMain.handle("viza:selectExportPath", async (_event, defaultName = "methodology.viza") => {
  const window = BrowserWindow.getFocusedWindow() ?? mainWindow;
  const methodologyDirectory = await ensureMethodologyDirectory();
  const result = await dialog.showSaveDialog(window, {
    title: "Export VIZA File",
    defaultPath: path.join(methodologyDirectory, slugify(defaultName).replace(/-viza$/, "") + ".viza"),
    filters: [
      { name: "VIZA File", extensions: ["viza"] },
      { name: "All Files", extensions: ["*"] },
    ],
  });

  if (result.canceled || !result.filePath) {
    return { canceled: true };
  }

  return { canceled: false, path: result.filePath };
});

ipcMain.handle("viza:desktopStatus", async () => {
  return desktopStatusPayload();
});

ipcMain.handle("viza:restartEngine", async () => {
  engineRuntimeMode = "restarting";
  stopEngineService();
  await startEngineService();
  return desktopStatusPayload();
});

function slugify(value) {
  return String(value)
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 80) || "untitled-methodology";
}

async function startEngineService() {
  if (process.env.VIZA_ENGINE_AUTOSTART === "0") {
    engineRuntimeMode = process.env.VIZA_ENGINE_URL ? "external" : "autostart_disabled";
    return;
  }
  if (engineProcess) {
    return;
  }

  engineLaunchError = "";
  const engineRoot = getEngineRoot();
  const host = process.env.VIZA_ENGINE_HOST || "127.0.0.1";
  const preferredPort = parseEnginePort(process.env.VIZA_ENGINE_PORT, 8765);
  const port = await findAvailablePort({ host, preferredPort });
  engineBaseUrl = resolveEngineBaseUrl(host, port);
  engineToken = createEngineToken();
  const engineCommand = resolveEngineCommand({
    engineRoot,
    platform: process.platform,
    pythonOverride: process.env.VIZA_PYTHON || "",
  });
  engineRuntimeMode = engineCommand.usesBundledRuntime ? "bundled_sidecar" : "system_python";
  if (
    !engineCommand.usesBundledRuntime &&
    !fsSync.existsSync(path.join(engineRoot, "viza", "service.py"))
  ) {
    engineLaunchError = `VIZA engine service was not found under ${engineRoot}.`;
    engineRuntimeMode = "start_failed";
    return;
  }

  const logFile = prepareEngineLogFile();
  try {
    const engineEnv = resolveEngineEnvironment({
      currentEnv: process.env,
      engineRoot,
      host,
      port,
      token: engineToken,
    });
    engineProcess = spawn(engineCommand.command, engineCommand.args, {
      cwd: engineRoot,
      env: {
        ...engineEnv,
        PYTHONPATH: prependPythonPath(engineRoot, process.env.PYTHONPATH || ""),
      },
      stdio: ["ignore", logFile.fd, logFile.fd],
      windowsHide: true,
    });
  } catch (error) {
    engineLaunchError = error instanceof Error ? error.message : "VIZA engine failed to start.";
    engineRuntimeMode = "start_failed";
    return;
  }

  const activeProcess = engineProcess;
  activeProcess.on("exit", () => {
    if (engineProcess === activeProcess) {
      engineProcess = null;
      engineRuntimeMode = "exited";
    }
  });
  activeProcess.on("error", (error) => {
    engineLaunchError = error.message;
    engineRuntimeMode = "start_failed";
    if (engineProcess === activeProcess) {
      engineProcess = null;
    }
  });

  try {
    await waitForEngineHealth({ baseUrl: engineBaseUrl, token: engineToken, timeoutMs: 12000 });
    engineLaunchError = "";
  } catch (error) {
    engineLaunchError = error instanceof Error ? error.message : "VIZA engine did not become ready.";
    stopEngineService();
    engineRuntimeMode = "start_failed";
  }
}

function stopEngineService() {
  if (engineProcess) {
    const processToStop = engineProcess;
    engineProcess = null;
    processToStop.kill();
    engineRuntimeMode = "stopped";
    engineToken = "";
  } else if (engineRuntimeMode !== "autostart_disabled" && engineRuntimeMode !== "external") {
    engineRuntimeMode = "stopped";
    engineToken = "";
  }
}

async function desktopStatusPayload() {
  return {
    appName: app.getName(),
    appPath: app.getAppPath(),
    appVersion: app.getVersion(),
    arch: process.arch,
    engineAutostart: process.env.VIZA_ENGINE_AUTOSTART !== "0",
    engineBaseUrl,
    engineLaunchError,
    engineLogPath,
    enginePid: engineProcess?.pid ?? null,
    engineRoot: getEngineRoot(),
    engineRuntimeMode,
    engineToken,
    engineTokenConfigured: Boolean(engineToken),
    isPackaged: app.isPackaged,
    methodologyDirectory: await ensureMethodologyDirectory(),
    platform: process.platform,
    userDataPath: app.getPath("userData"),
  };
}

async function ensureMethodologyDirectory() {
  const methodologyDirectory = resolveMethodologyDirectory(app);
  await fs.mkdir(methodologyDirectory, { recursive: true });
  return methodologyDirectory;
}

function getEngineRoot() {
  return resolveEngineRoot({
    currentDir: __dirname,
    isPackaged: app.isPackaged,
    resourcesPath: process.resourcesPath,
  });
}

function prepareEngineLogFile() {
  const logDirectory = path.join(app.getPath("userData"), "logs");
  fsSync.mkdirSync(logDirectory, { recursive: true });
  engineLogPath = path.join(logDirectory, "viza-engine.log");
  return {
    fd: fsSync.openSync(engineLogPath, "a"),
    path: engineLogPath,
  };
}

function waitForEngineHealth({ baseUrl, token, timeoutMs }) {
  const deadline = Date.now() + timeoutMs;

  return new Promise((resolve, reject) => {
    const poll = () => {
      requestEngineHealth({ baseUrl, token })
        .then(resolve)
        .catch((error) => {
          if (Date.now() >= deadline) {
            reject(error);
            return;
          }
          setTimeout(poll, 250);
        });
    };
    poll();
  });
}

function requestEngineHealth({ baseUrl, token }) {
  return new Promise((resolve, reject) => {
    const url = new URL("/health", baseUrl);
    const request = http.get(
      url,
      {
        headers: token ? { "x-viza-engine-token": token } : {},
        timeout: 1500,
      },
      (response) => {
        response.resume();
        if (response.statusCode === 200) {
          resolve();
          return;
        }
        reject(new Error(`VIZA engine health returned ${response.statusCode}.`));
      },
    );

    request.on("timeout", () => {
      request.destroy(new Error("VIZA engine health check timed out."));
    });
    request.on("error", reject);
  });
}
