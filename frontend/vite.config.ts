import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/generate-meme": "http://127.0.0.1:8000",
      "/feed": "http://127.0.0.1:8000",
      "/auto-toggle": "http://127.0.0.1:8000",
      "/auto-status": "http://127.0.0.1:8000",
      "/trending": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
    },
  },
});
