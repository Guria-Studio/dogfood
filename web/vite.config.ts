import { tanstackRouter } from "@tanstack/router-plugin/vite";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vitest/config";

const BACKEND = "http://127.0.0.1:7470";

export default defineConfig({
  plugins: [
    tanstackRouter({ target: "react", autoCodeSplitting: true }),
    react(),
    tailwindcss(),
  ],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  build: { outDir: "../src/dogfood/panel/estatico", emptyOutDir: true },
  server: {
    proxy: {
      "/api": BACKEND,
      "/archivos": BACKEND,
      "/dispositivos": BACKEND,
      "/ws": { target: BACKEND, ws: true },
    },
  },
  test: {
    testTimeout: 30000,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    exclude: ["e2e/**", "node_modules/**"],
  },
});
