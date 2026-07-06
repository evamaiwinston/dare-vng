import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev-only config for the playground (the published package is built by tsup).
// root = playground so its index.html is the dev entry; it imports ../src directly.
export default defineConfig({
  root: "playground",
  plugins: [react()],
  server: { host: true, port: 5173 },
});
