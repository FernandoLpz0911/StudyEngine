import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The frontend calls /api/*; Vite proxies that to the FastAPI backend on :8000,
// which serves those routes under the same /api prefix. Start the backend with:
// uvicorn engine.api:app  — or run the whole app via: python -m engine.cli.app
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
