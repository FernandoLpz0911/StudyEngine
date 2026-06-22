import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The frontend calls /api/*; Vite proxies that to the FastAPI backend on :8000,
// stripping the /api prefix. Start the backend with: uvicorn engine.api:app
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
