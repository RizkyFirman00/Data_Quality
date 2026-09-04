import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { allowedHosts: ["be9e-103-164-12-203.ngrok-free.app"] },
});
