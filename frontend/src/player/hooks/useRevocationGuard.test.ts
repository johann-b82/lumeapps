// Unit coverage for the revocation debounce (useRevocationGuard).
//
// The guard's contract: a still-valid, non-expiring device token must survive a
// TRANSIENT 401 (server restart / DB restore / reboot race) and only be cleared
// once 401s persist continuously for REVOKE_CONFIRM_MS with no successful authed
// response in between. These tests pin exactly that boundary.

import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { REVOKE_CONFIRM_MS, useRevocationGuard } from "./useRevocationGuard";

describe("useRevocationGuard", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(0);
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("does not revoke on the first 401", () => {
    const onRevoke = vi.fn();
    const { result } = renderHook(() => useRevocationGuard(onRevoke));

    result.current.onUnauthorized();

    expect(onRevoke).not.toHaveBeenCalled();
  });

  it("does not revoke while 401s stay within the confirm window", () => {
    const onRevoke = vi.fn();
    const { result } = renderHook(() => useRevocationGuard(onRevoke));

    result.current.onUnauthorized(); // first strike arms the clock
    vi.advanceTimersByTime(REVOKE_CONFIRM_MS - 1_000);
    result.current.onUnauthorized(); // still inside the window

    expect(onRevoke).not.toHaveBeenCalled();
  });

  it("revokes once 401s persist beyond the confirm window", () => {
    const onRevoke = vi.fn();
    const { result } = renderHook(() => useRevocationGuard(onRevoke));

    result.current.onUnauthorized(); // arms the clock at t=0
    vi.advanceTimersByTime(REVOKE_CONFIRM_MS);
    result.current.onUnauthorized(); // now sustained long enough

    expect(onRevoke).toHaveBeenCalledTimes(1);
  });

  it("forgives a transient 401 after a successful authed response", () => {
    const onRevoke = vi.fn();
    const { result } = renderHook(() => useRevocationGuard(onRevoke));

    result.current.onUnauthorized(); // transient blip arms the clock
    vi.advanceTimersByTime(REVOKE_CONFIRM_MS + 60_000);
    result.current.noteAuthSuccess(); // server recovered — clock resets

    // A later 401 is treated as a fresh first strike, not an aged one.
    result.current.onUnauthorized();
    expect(onRevoke).not.toHaveBeenCalled();

    // ...and only revokes if THAT streak now persists on its own.
    vi.advanceTimersByTime(REVOKE_CONFIRM_MS);
    result.current.onUnauthorized();
    expect(onRevoke).toHaveBeenCalledTimes(1);
  });

  it("re-arms after a confirmed revoke instead of firing every subsequent 401", () => {
    const onRevoke = vi.fn();
    const { result } = renderHook(() => useRevocationGuard(onRevoke));

    result.current.onUnauthorized();
    vi.advanceTimersByTime(REVOKE_CONFIRM_MS);
    result.current.onUnauthorized(); // confirmed → fires once, clock cleared
    result.current.onUnauthorized(); // immediately after → new first strike, no fire

    expect(onRevoke).toHaveBeenCalledTimes(1);
  });
});
