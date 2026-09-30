import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import tsconfigPaths from "vite-tsconfig-paths";

// The LMS Flask API runs on :5060 (the CRM API uses :5050). Proxying /api keeps the
// frontend and API on one origin, so no CORS is needed in dev or behind the production reverse proxy.
const API_TARGET = process.env["VITE_API_TARGET"] ?? "http://127.0.0.1:5060";

export default defineConfig({
  plugins: [tanstackRouter({ target: "react", autoCodeSplitting: true }), react(), tailwindcss(), tsconfigPaths()],
  server: { port: 5174, proxy: { "/api": { target: API_TARGET, changeOrigin: true } } },
  preview: { port: 4174, proxy: { "/api": { target: API_TARGET, changeOrigin: true } } },
});
