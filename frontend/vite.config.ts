import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { VitePWA } from "vite-plugin-pwa";
import path from "path";

// Phase 47 build invariants:
//  1. admin build MUST run before player build (Pitfall P3 — admin wipes dist/ which would also wipe dist/player/).
//  2. base + scope MUST both be '/player/' for the player bundle (Pitfall P2 — SW won't register otherwise).
//  3. VitePWA is conditionally registered ONLY for the player mode — admin must never get a Service Worker.
//  4. manualChunks emits TWO physical copies of vendor-react (one per outDir). This is intentional per OQ2 resolution.
//  5. cacheName 'signage-playlist-v1' — BUMP to v2 when /playlist envelope shape changes (Pitfall P8).
export default defineConfig(({ mode }) => {
  const isPlayer = mode === "player";
  return {
    base: isPlayer ? "/player/" : "/",
    build: {
      outDir: isPlayer ? "dist/player" : "dist",
      emptyOutDir: true,
      rollupOptions: {
        // Player mode: build from player.html (separate source from admin's
        // index.html). Post-build step in package.json renames
        // dist/player/player.html → dist/player/index.html so the SW
        // registration script + Workbox navigateFallback resolve correctly
        // (Pitfall P2 — PWA expects index.html at the scope root).
        input: isPlayer
          ? path.resolve(__dirname, "player.html")
          : path.resolve(__dirname, "index.html"),
        output: {
          manualChunks(id: string) {
            if (id.includes("node_modules")) {
              if (
                id.includes("/react/") ||
                id.includes("/react-dom/") ||
                id.includes("/scheduler/") ||
                id.includes("/@tanstack/react-query/")
              ) {
                return "vendor-react";
              }
            }
            return undefined;
          },
        },
      },
    },
    plugins: [
      react(),
      tailwindcss(),
      ...(isPlayer
        ? [
            VitePWA({
              registerType: "autoUpdate",
              scope: "/player/",
              base: "/player/",
              manifest: {
                name: "Signage Player",
                short_name: "Signage",
                start_url: "/player/",
                display: "fullscreen",
                background_color: "#0a0a0a",
                theme_color: "#0a0a0a",
                icons: [
                  { src: "/player/icon-192.png", sizes: "192x192", type: "image/png" },
                ],
              },
              workbox: {
                navigateFallback: "/player/index.html",
                // Cache name is versioned: bump to v2 when the /playlist envelope shape changes (Pitfall P8).
                runtimeCaching: [
                  {
                    // Matches /api/signage/player/playlist (Phase 43 player polling endpoint).
                    urlPattern: /\/api\/signage\/player\/playlist/,
                    handler: "StaleWhileRevalidate",
                    options: {
                      cacheName: "signage-playlist-v1",
                      expiration: { maxEntries: 5, maxAgeSeconds: 86400 },
                      cacheableResponse: { statuses: [0, 200] },
                    },
                  },
                ],
              },
            }),
          ]
        : []),
    ],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      host: "0.0.0.0",
      proxy: {
        "/api": {
          target: process.env.VITE_API_TARGET || "http://api:8000",
          changeOrigin: true,
        },
      },
    },
  };
});
