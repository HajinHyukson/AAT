const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("vizaDesktop", {
  desktopStatus: () => ipcRenderer.invoke("viza:desktopStatus"),
  openGraph: () => ipcRenderer.invoke("viza:openGraph"),
  restartEngine: () => ipcRenderer.invoke("viza:restartEngine"),
  saveGraph: (graph) => ipcRenderer.invoke("viza:saveGraph", graph),
  selectExportPath: (defaultName) => ipcRenderer.invoke("viza:selectExportPath", defaultName),
  selectVizaFile: () => ipcRenderer.invoke("viza:selectVizaFile"),
});
