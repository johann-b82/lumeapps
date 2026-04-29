// Phase 47 UI-SPEC §Routing Contract: wouter Switch with two routes + fallback.
// Backend serves dist/player/index.html for ANY /player/* path (Pattern 5 SPA fallback);
// wouter parses :token client-side.

import { Switch, Route, Router } from "wouter";
import { PairingScreen } from "@/player/PairingScreen";
import { PlaybackShell } from "@/player/PlaybackShell";

export function PlayerApp() {
  return (
    // Vite base is /player/ for this entry; wouter routes are relative to that base.
    // Use Router base="/player" so paths inside the Switch are relative to /player/.
    <Router base="/player">
      <Switch>
        {/* "/" inside the /player base = full URL "/player/" → pairing surface */}
        <Route path="/" component={PairingScreen} />
        {/* "/:token" → "/player/<token>" → playback */}
        <Route path="/:token" component={PlaybackShell} />
        {/* Fallback for anything else under /player/* — render pairing surface (D-2 fallback) */}
        <Route component={PairingScreen} />
      </Switch>
    </Router>
  );
}
