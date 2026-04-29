// Phase 46-03 originally hardcoded `loop`. Phase 47 P12 made it a prop:
//   - admin preview keeps backward-compat default (loop=true)
//   - player wrapper (frontend/src/player/PlaybackShell.tsx) passes loop=false
//     so video plays once and `onEnded` advances the playlist (D-6 VIDEO_DURATION_NATURAL).
export interface VideoPlayerProps {
  uri: string | null;
  /** When true (default), the video element loops. Admin preview relies on this
   *  backward-compatible default; the Phase 47 player wrapper passes `false`
   *  and uses `onEnded` to advance the playlist (D-6 video sentinel). */
  loop?: boolean;
  /** Fires on natural video end (only meaningful when `loop={false}`). */
  onEnded?: () => void;
  /** Phase 62 D-05 / CAL-PI-06: when false (default) the `<video>` element is
   *  muted at the HTMLMediaElement level — this preserves autoplay-compliance
   *  and the Phase 47 invariant that kiosk videos auto-play silent. When the
   *  admin UI flips `audio_enabled=true` the SSE `calibration-changed` event
   *  refetches calibration and passes `muted={false}` down; `wpctl` handles
   *  the system sink mute in parallel on the Pi sidecar. */
  muted?: boolean;
}

export function VideoPlayer({ uri, loop = true, onEnded, muted = true }: VideoPlayerProps) {
  if (!uri) return null;
  return (
    <video
      src={uri}
      muted={muted}
      autoPlay
      playsInline
      loop={loop}
      onEnded={onEnded}
      className="w-full h-full object-contain"
    />
  );
}
