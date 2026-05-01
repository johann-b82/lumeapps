// frontend/src/hooks/__tests__/useSettingsSection.test.tsx
import { describe, it, expect } from "vitest";
import { renderHook } from "@testing-library/react";
import { Router } from "wouter";
import { memoryLocation } from "wouter/memory-location";
import { useSettingsSection } from "@/hooks/useSettingsSection";

function makeWrapper(path: string) {
  const memory = memoryLocation({ path, record: true });
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <Router hook={memory.hook}>{children}</Router>
  );
  return { Wrapper, memory };
}

describe("useSettingsSection", () => {
  it("returns 'general' for /settings (the redirect target)", () => {
    const { Wrapper } = makeWrapper("/settings");
    const { result } = renderHook(() => useSettingsSection(), { wrapper: Wrapper });
    expect(result.current.section).toBe("general");
  });

  it("returns 'general' for /settings/general", () => {
    const { Wrapper } = makeWrapper("/settings/general");
    const { result } = renderHook(() => useSettingsSection(), { wrapper: Wrapper });
    expect(result.current.section).toBe("general");
  });

  it("returns 'hr' for /settings/hr", () => {
    const { Wrapper } = makeWrapper("/settings/hr");
    const { result } = renderHook(() => useSettingsSection(), { wrapper: Wrapper });
    expect(result.current.section).toBe("hr");
  });

  it("returns 'sensors' for /settings/sensors", () => {
    const { Wrapper } = makeWrapper("/settings/sensors");
    const { result } = renderHook(() => useSettingsSection(), { wrapper: Wrapper });
    expect(result.current.section).toBe("sensors");
  });

  it("returns 'general' for any unknown /settings/<x>", () => {
    const { Wrapper } = makeWrapper("/settings/unknown");
    const { result } = renderHook(() => useSettingsSection(), { wrapper: Wrapper });
    expect(result.current.section).toBe("general");
  });
});
