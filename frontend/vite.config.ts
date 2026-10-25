import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    // Ensure .tsx and .ts files are found when imported without an extension
    extensions: [".ts", ".tsx", ".js", ".jsx"],
  },
  server: {
    port: 5173,
    // Proxy API requests to the backend during development.
    // This avoids CORS issues — the browser calls /api/v1/* on the
    // frontend dev server, and Vite forwards them to the backend.
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    // Use jsdom to simulate a browser environment (DOM, localStorage, etc.)
    environment: "jsdom",
    // Import @testing-library/jest-dom matchers (toBeInTheDocument, etc.)
    // in every test file automatically.
    setupFiles: ["./src/test/setup.ts"],
    globals: true,
  },
});
