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
                // The build emits the player entry as player.html, then renames it
                // to index.html AFTER Vite (and this plugin) run — so the generated
                // precache manifest references "player.html" while navigateFallback
                // points at "/player/index.html". Workbox's createHandlerBoundToURL
                // then throws `non-precached-url` at SW-evaluation time because
                // /player/index.html isn't in the manifest, and the service worker
                // fails to install — killing ALL offline support (blank kiosk after
                // the server goes down + a Chromium restart). Rewrite that one entry
                // to index.html so the manifest matches both navigateFallback and the
                // renamed file on disk. The content (and thus revision hash) is
                // identical — only the filename changes.
                manifestTransforms: [
                  (entries) => ({
                    manifest: entries.map((e) =>
                      e.url === "player.html" ? { ...e, url: "index.html" } : e,
                    ),
                    warnings: [],
                  }),
                ],
                // Kiosk Pis never navigate; the default "wait until all pages close"
                // SW activation leaves them on stale chunks forever. Skip-wait +
                // claim makes the new build take over on the next reload.
                skipWaiting: true,
                clientsClaim: true,
                // Cache name is versioned: bump to v2 when the /playlist envelope shape changes (Pitfall P8).
                runtimeCaching: [
                  {
                    // Matches /api/signage/player/playlist (Phase 43 player polling endpoint).
                    urlPattern: /\/api\/signage\/player\/playlist/,
                    handler: "StaleWhileRevalidate",
                    options: {
                      // 1-year expiry (not 24h): offline playback must survive
                      // indefinitely, not just one day. StaleWhileRevalidate still
                      // refreshes the cache silently whenever the kiosk is online.
                      cacheName: "signage-playlist-v1",
                      expiration: { maxEntries: 5, maxAgeSeconds: 60 * 60 * 24 * 365 },
                      cacheableResponse: { statuses: [0, 200] },
                    },
                  },
                  {
                    // Matches /api/signage/player/asset/<uuid> and .../asset/<uuid>/slide/<idx>
                    // (device-auth'd media + PPTX slide passthrough). Without this the media
                    // only lives in the browser HTTP cache, which honours the backend's
                    // Cache-Control: max-age=300 and goes stale after 5 minutes offline —
                    // breaking playback. CacheFirst serves from the SW cache regardless of
                    // network, so offline playback works infinitely.
                    //
                    // Media is content-addressed by UUID (new content ⇒ new id), so a cached
                    // entry never goes stale. matchOptions.ignoreSearch drops the rotating
                    // ?token=… query from the cache key, so token rotation while online neither
                    // bloats the cache nor forces a re-fetch of already-cached media.
                    urlPattern: /\/api\/signage\/player\/asset\//,
                    handler: "CacheFirst",
                    options: {
                      cacheName: "signage-media-v1",
                      matchOptions: { ignoreSearch: true },
                      expiration: {
                        maxEntries: 200,
                        maxAgeSeconds: 60 * 60 * 24 * 365,
                        purgeOnQuotaError: true,
                      },
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
      // Allow any Host header. The signage URL renderer (headless Chromium in
      // the api container) loads internal /embed pages via the `frontend`
      // service host; Vite's default host check would 403 those. This is an
      // internal LAN tool behind Caddy, so DNS-rebinding risk is acceptable.
      allowedHosts: true,
      // Bind-mount fs events from the Windows host into the Linux container don't
      // propagate reliably through Docker Desktop's gRPC FUSE — Vite's inotify-based
      // watcher silently misses edits and serves stale transforms until the dev server
      // is restarted. Polling is a few % extra CPU but never misses an event.
      watch: { usePolling: true, interval: 300 },
      proxy: {
        "/api": {
          target: process.env.VITE_API_TARGET || "http://api:8000",
          changeOrigin: true,
        },
        "/directus": {
          target: process.env.VITE_DIRECTUS_TARGET || "http://directus:8055",
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/directus/, ""),
        },
        // Embedded apps live behind Caddy with forward_auth in front. In dev
        // (localhost:5173) Vite catch-alls everything to the SPA, so /paperless,
        // /pdf, /op would return the admin shell. Proxy through Caddy so the
        // launcher tiles "just work" on the dev port too.
        // `changeOrigin: false` keeps the original Host header. OpenProject
        // validates Host against OPENPROJECT_HOST__NAME=localhost and rejects
        // proxied requests where the rewritten Host is `caddy:80` (400 Bad
        // Request). Caddy itself does not care about Host so leaving it as
        // `localhost:5173` works for paperless and stirling too.
        "/paperless": {
          target: process.env.VITE_CADDY_TARGET || "http://caddy:80",
          changeOrigin: false,
        },
        "/pdf": {
          target: process.env.VITE_CADDY_TARGET || "http://caddy:80",
          changeOrigin: false,
        },
        "/op": {
          target: process.env.VITE_CADDY_TARGET || "http://caddy:80",
          changeOrigin: false,
        },
      },
    },
  };
});
