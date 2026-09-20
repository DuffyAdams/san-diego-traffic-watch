import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { createMockApiHandler } from "./mocks/api.mjs";

export default defineConfig(({ mode, command, isPreview }) => {
  const useMocks = command === "serve" && !isPreview &&
    (mode === "mock" || (mode === "development" && !process.env.VITE_PROD_URL));
  const proxyTarget =
    process.env.VITE_PROD_URL ||
    (mode === "proxy"
      ? "https://sandiegotraffic.com"
      : "http://127.0.0.1:5002");

  return {
    plugins: [
      svelte(),
      ...(useMocks ? [{
        name: "traffic-mock-api",
        configureServer(server) {
          const handleRequest = createMockApiHandler();
          server.middlewares.use((req, res, next) => {
            if (req.url?.startsWith("/api/") || req.url?.startsWith("/maps/") || req.url === "/__reset") {
              return handleRequest(req, res).catch(next);
            }
            next();
          });
          server.config.logger.info("Mock traffic data enabled — no Python server needed.");
        },
      }] : []),
    ],
    define: {
      "import.meta.env.VITE_MOCK_DATA": JSON.stringify(useMocks),
    },
    build: {
      // MapLibre is already lazy-loaded into its own chunk; its renderer is
      // intentionally larger than Vite's generic warning threshold.
      chunkSizeWarningLimit: 1100,
    },
    optimizeDeps: {
      include: ["lucide-svelte"],
    },
    server: {
      host: process.env.VITE_DEV_HOST || "0.0.0.0",
      port: Number(process.env.VITE_DEV_PORT || 5173),
      strictPort: true,
      allowedHosts: ["traffic-app.duffyadams.com"],
      proxy: useMocks ? undefined : {
        "/api": {
          target: proxyTarget,
          changeOrigin: true,
        },
        "/maps": {
          target: proxyTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
