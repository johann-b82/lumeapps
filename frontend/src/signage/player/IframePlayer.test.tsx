import { act, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { IframePlayer } from "./IframePlayer";

describe("IframePlayer — embed cycle / safety backstop", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("advances on the embed-cycle-complete postMessage", () => {
    const onCycleEnd = vi.fn();
    render(
      <IframePlayer uri="http://x/embed/joiners" durationS={10} onCycleEnd={onCycleEnd} />,
    );
    expect(onCycleEnd).not.toHaveBeenCalled();
    act(() => {
      window.dispatchEvent(
        new MessageEvent("message", { data: { type: "embed-cycle-complete" } }),
      );
    });
    expect(onCycleEnd).toHaveBeenCalledTimes(1);
  });

  it("advances via the safety backstop when the embed never posts", () => {
    const onCycleEnd = vi.fn();
    render(
      <IframePlayer uri="http://x/embed/birthdays" durationS={10} onCycleEnd={onCycleEnd} />,
    );
    // Well before the 120s floor: still waiting.
    act(() => vi.advanceTimersByTime(60_000));
    expect(onCycleEnd).not.toHaveBeenCalled();
    // After the floor: advance anyway so the playlist never freezes.
    act(() => vi.advanceTimersByTime(60_000));
    expect(onCycleEnd).toHaveBeenCalledTimes(1);
  });

  it("does not double-fire when a message arrives before the backstop", () => {
    const onCycleEnd = vi.fn();
    render(
      <IframePlayer uri="http://x/embed/worldcup" durationS={10} onCycleEnd={onCycleEnd} />,
    );
    act(() => {
      window.dispatchEvent(
        new MessageEvent("message", { data: { type: "embed-cycle-complete" } }),
      );
    });
    act(() => vi.advanceTimersByTime(300_000));
    expect(onCycleEnd).toHaveBeenCalledTimes(1);
  });
});
