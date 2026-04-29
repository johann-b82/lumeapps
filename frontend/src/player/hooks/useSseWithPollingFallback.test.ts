// Phase 62 Plan 04 — unit coverage for the player SSE hook extension.
//
// These tests pin three behaviours of the `onmessage` handler:
//   1. `calibration-changed` dispatches `onCalibrationChanged` (CAL-PI-06 D-05).
//   2. `calibration-changed` does NOT dispatch `onPlaylistInvalidated` (no crosstalk).
//   3. `playlist-changed` still dispatches `onPlaylistInvalidated` (regression guard).
//
// We install a minimal global `EventSource` stub so `new EventSource(url)` gives
// us a reference we can drive `.onmessage(...)` against. jsdom doesn't ship an
// EventSource, so the stub is also necessary for the hook to run at all.

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useSseWithPollingFallback } from "./useSseWithPollingFallback";

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  url: string;
  onopen: ((e: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  readyState = 0;
  closed = false;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }
  close() {
    this.closed = true;
  }
}

describe("useSseWithPollingFallback — calibration-changed dispatch", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    // @ts-expect-error — test-only global install
    globalThis.EventSource = FakeEventSource;
  });

  afterEach(() => {
    // @ts-expect-error — cleanup
    delete globalThis.EventSource;
    vi.restoreAllMocks();
  });

  it("dispatches onCalibrationChanged when SSE event is calibration-changed", () => {
    const onPlaylistInvalidated = vi.fn();
    const onCalibrationChanged = vi.fn();
    const onUnauthorized = vi.fn();

    renderHook(() =>
      useSseWithPollingFallback({
        token: "test-token",
        streamUrl: "/api/signage/player/stream",
        pollUrl: "/api/signage/player/playlist",
        onPlaylistInvalidated,
        onCalibrationChanged,
        onUnauthorized,
      }),
    );

    const es = FakeEventSource.instances[0];
    expect(es).toBeDefined();

    act(() => {
      es.onmessage?.(
        new MessageEvent("message", {
          data: JSON.stringify({
            event: "calibration-changed",
            device_id: "abc-123",
          }),
        }),
      );
    });

    expect(onCalibrationChanged).toHaveBeenCalledTimes(1);
  });

  it("does NOT dispatch onPlaylistInvalidated on calibration-changed event", () => {
    const onPlaylistInvalidated = vi.fn();
    const onCalibrationChanged = vi.fn();
    const onUnauthorized = vi.fn();

    renderHook(() =>
      useSseWithPollingFallback({
        token: "test-token",
        streamUrl: "/api/signage/player/stream",
        pollUrl: "/api/signage/player/playlist",
        onPlaylistInvalidated,
        onCalibrationChanged,
        onUnauthorized,
      }),
    );

    const es = FakeEventSource.instances[0];
    act(() => {
      es.onmessage?.(
        new MessageEvent("message", {
          data: JSON.stringify({
            event: "calibration-changed",
            device_id: "abc-123",
          }),
        }),
      );
    });

    expect(onPlaylistInvalidated).not.toHaveBeenCalled();
  });

  it("still dispatches onPlaylistInvalidated on playlist-changed (regression guard)", () => {
    const onPlaylistInvalidated = vi.fn();
    const onCalibrationChanged = vi.fn();
    const onUnauthorized = vi.fn();

    renderHook(() =>
      useSseWithPollingFallback({
        token: "test-token",
        streamUrl: "/api/signage/player/stream",
        pollUrl: "/api/signage/player/playlist",
        onPlaylistInvalidated,
        onCalibrationChanged,
        onUnauthorized,
      }),
    );

    const es = FakeEventSource.instances[0];
    act(() => {
      es.onmessage?.(
        new MessageEvent("message", {
          data: JSON.stringify({
            event: "playlist-changed",
            playlist_id: "pl-1",
            etag: "deadbeef",
          }),
        }),
      );
    });

    expect(onPlaylistInvalidated).toHaveBeenCalledTimes(1);
    expect(onCalibrationChanged).not.toHaveBeenCalled();
  });
});
