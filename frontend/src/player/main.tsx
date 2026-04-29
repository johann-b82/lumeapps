// Phase 47 player entry. Final wiring (replaces Plan 47-01 bootstrap skeleton).
// pdfWorker import MUST come first — pins GlobalWorkerOptions before any PdfPlayer mounts.

import "./lib/pdfWorker";
// DEFECT-1: player entry must pull in the Tailwind entry — otherwise every
// utility class in the player is a no-op (pairing code renders as 16px Times,
// playback canvas drops `bg-black`, etc.).
import "../index.css";
import { createRoot } from "react-dom/client";
import { StrictMode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PlayerApp } from "./App";

const rootEl = document.getElementById("player-root");
if (!rootEl) {
  throw new Error("Phase 47: #player-root element missing from player.html");
}

// Player query client: aggressive retain (offline cache-and-loop relies on never evicting
// the last-known playlist while the page is mounted).
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      gcTime: Infinity,
      staleTime: 5 * 60_000,
      retry: 2,
      refetchOnWindowFocus: false, // kiosk never has window focus changes
    },
  },
});

createRoot(rootEl).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <PlayerApp />
    </QueryClientProvider>
  </StrictMode>,
);
