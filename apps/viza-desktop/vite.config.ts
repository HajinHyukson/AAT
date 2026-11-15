import { fileURLToPath, URL } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const repoRoot = fileURLToPath(new URL("../..", import.meta.url));

export default defineConfig({
  base: "./",
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5174,
    strictPort: true,
    fs: {
      allow: [repoRoot],
    },
  },
  preview: {
    host: "127.0.0.1",
    port: 4174,
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
