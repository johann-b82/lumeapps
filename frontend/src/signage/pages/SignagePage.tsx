import { MediaPage } from "./MediaPage";
import { PlaylistsPage } from "./PlaylistsPage";
import { DevicesPage } from "./DevicesPage";
import { SchedulesPage } from "./SchedulesPage";

type SignageTab = "media" | "playlists" | "devices" | "schedules";

interface SignagePageProps {
  initialTab: SignageTab;
}

/**
 * Phase 46 SGN-ADM-03 / D-04: Signage tab shell.
 * URL is the source of truth — App.tsx's <Route> picks which tab via `initialTab` prop.
 * Custom 4-tab SegmentedControl lives in <SubHeader /> (moved 2026-04-22 — h1 removed and pill hoisted for chrome consistency with /sales, /hr, /sensors).
 */
export function SignagePage({ initialTab }: SignagePageProps) {
  const active: SignageTab = initialTab;

  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-16 space-y-6">
      {active === "media" && <MediaPage />}
      {active === "playlists" && <PlaylistsPage />}
      {active === "devices" && <DevicesPage />}
      {active === "schedules" && <SchedulesPage />}
    </div>
  );
}
