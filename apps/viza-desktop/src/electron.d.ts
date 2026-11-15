import type { VizaMethodologyGraph } from "./vizaGraph";

export interface VizaDesktopSaveResult {
  canceled: boolean;
  path?: string;
}

export interface VizaDesktopOpenResult {
  canceled: boolean;
  path?: string;
  graph?: unknown;
}

export interface VizaDesktopPathResult {
  canceled: boolean;
  path?: string;
}

export interface VizaDesktopStatus {
  appName: string;
  appPath: string;
  appVersion: string;
  arch: string;
  engineAutostart: boolean;
  engineBaseUrl: string;
  engineLaunchError: string;
  engineLogPath: string;
  enginePid: number | null;
  engineRoot: string;
  engineRuntimeMode: string;
  engineToken: string;
  engineTokenConfigured: boolean;
  isPackaged: boolean;
  methodologyDirectory: string;
  platform: string;
  userDataPath: string;
}

declare global {
  interface Window {
    vizaDesktop?: {
      desktopStatus: () => Promise<VizaDesktopStatus>;
      openGraph: () => Promise<VizaDesktopOpenResult>;
      restartEngine: () => Promise<VizaDesktopStatus>;
      saveGraph: (graph: VizaMethodologyGraph) => Promise<VizaDesktopSaveResult>;
      selectExportPath: (defaultName?: string) => Promise<VizaDesktopPathResult>;
      selectVizaFile: () => Promise<VizaDesktopPathResult>;
    };
  }
}
