import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import {
  SettingsDraftProvider,
  useSettingsDraftStatus,
} from "@/contexts/SettingsDraftContext";

describe("SettingsDraftContext", () => {
  it("requestSectionChange with isDirty=false navigates immediately (pendingSection stays null)", () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <SettingsDraftProvider>{children}</SettingsDraftProvider>
    );
    const { result } = renderHook(() => useSettingsDraftStatus(), { wrapper });
    expect(result.current).not.toBeNull();
    expect(result.current!.pendingSection).toBeNull();
    expect(result.current!.isDirty).toBe(false);

    let navigated: string | null = null;
    act(() => {
      result.current!.requestSectionChange("hr", (dest) => {
        navigated = dest;
      });
    });
    expect(navigated).toBe("/settings/hr");
    expect(result.current!.pendingSection).toBeNull();
  });

  it("requestSectionChange with isDirty=true defers via pendingSection", () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <SettingsDraftProvider>{children}</SettingsDraftProvider>
    );
    const { result } = renderHook(() => useSettingsDraftStatus(), { wrapper });

    act(() => result.current!.setDirty(true));
    let navigated: string | null = null;
    act(() => {
      result.current!.requestSectionChange("general", (dest) => {
        navigated = dest;
      });
    });
    expect(navigated).toBeNull();
    expect(result.current!.pendingSection).toBe("general");
  });

  it("clearPendingSection resets to null", () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <SettingsDraftProvider>{children}</SettingsDraftProvider>
    );
    const { result } = renderHook(() => useSettingsDraftStatus(), { wrapper });
    act(() => result.current!.setDirty(true));
    act(() =>
      result.current!.requestSectionChange("hr", () => {}),
    );
    expect(result.current!.pendingSection).toBe("hr");
    act(() => result.current!.clearPendingSection());
    expect(result.current!.pendingSection).toBeNull();
  });
});
