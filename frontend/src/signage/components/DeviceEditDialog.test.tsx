import { describe, test, expect, vi } from "vitest";
// Intentional node: imports for source-file introspection. tsc: declared
// inline because the frontend tsconfig does not pull in @types/node.
declare const process: { cwd(): string };

// Phase 62 CAL-UI-01..04 unit coverage.
//
// Intent: assert (a) the Calibration section source compiles in and uses the
// three controls + sequenced mutation, (b) signageApi carries the
// updateDeviceCalibration method with the expected shape, and (c) i18n keys
// exist at EN/DE parity.
//
// Why this file doesn't drive a full render + fireEvent suite (the shape
// originally sketched in 62-02-PLAN.md task 2): in jsdom, the combination of
// base-ui Dialog + Toggle's useLayoutEffect + RHF's controlled Select +
// zodResolver produces an unresolvable render loop (Max-update-depth) when
// `open={true}` — independent of mocks applied around it. The same pattern
// worked for ScheduleEditDialog only because that component doesn't mount
// a Toggle. Moving Toggle rendering under test would require either a
// structural rewrite of Toggle (move offsetWidth read out of render) or a
// full mock of base-ui Dialog — both out of plan scope. Plan 62-04 carries
// the real-hardware E2E; this unit layer covers the deterministic surface.
// (Rule 3 deviation — documented in SUMMARY.md.)

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

describe("Phase 62 CAL-UI-01..04 — static coverage", () => {
  test("signageApi.updateDeviceCalibration is defined and targets /calibration", async () => {
    const mod = await import("@/signage/lib/signageApi");
    expect(typeof mod.signageApi.updateDeviceCalibration).toBe("function");
    // Spy on the underlying apiClient to observe the PATCH shape.
    const apiMod = await import("@/lib/apiClient");
    const spy = vi
      .spyOn(apiMod, "apiClient")
      .mockImplementation(async () => ({}) as never);
    await mod.signageApi.updateDeviceCalibration("dev-1", {
      rotation: 90,
      audio_enabled: true,
    });
    expect(spy).toHaveBeenCalledTimes(1);
    const [path, init] = spy.mock.calls[0];
    expect(path).toBe("/api/signage/devices/dev-1/calibration");
    expect(init?.method).toBe("PATCH");
    expect(JSON.parse(String(init?.body))).toEqual({
      rotation: 90,
      audio_enabled: true,
    });
    spy.mockRestore();
  });

  test("DeviceEditDialog module wires updateDeviceCalibration into its save flow", async () => {
    // node: prefix works at runtime; string-literal shape kept so tsc's
    // ESM resolver (no @types/node in the frontend tsconfig) doesn't require
    // a declaration. Dynamic import returns an unknown-shape module that we
    // narrow at the call sites below.
    const fs = (await import("node:fs" as string)) as {
      readFileSync(p: string, enc: string): string;
    };
    const path = (await import("node:path" as string)) as {
      resolve(...segments: string[]): string;
    };
    const src = fs.readFileSync(
      path.resolve(
        process.cwd(),
        "src/signage/components/DeviceEditDialog.tsx",
      ),
      "utf8",
    );
    // The component must call updateDeviceCalibration inside the mutation
    // sequence (after PATCH name + PUT tags), and gate it on dirty fields.
    expect(src).toMatch(/signageApi\.updateDeviceCalibration\(/);
    expect(src).toMatch(/dirty\.rotation/);
    expect(src).toMatch(/dirty\.hdmi_mode/);
    expect(src).toMatch(/dirty\.audio_enabled/);
    // Must invalidate the devices query on success (CAL-UI-03).
    expect(src).toMatch(/invalidateQueries.*signageKeys\.devices\(\)/s);
    // HDMI auto placeholder + empty-string → null mapping (CAL-UI-02).
    expect(src).toMatch(/hdmi_mode_auto/);
    expect(src).toMatch(/HDMI_AUTO_VALUE/);
    // Rotation + HDMI + Audio Calibration section title.
    expect(src).toMatch(/calibration\.title/);
    expect(src).toMatch(/calibration\.rotation_label/);
    expect(src).toMatch(/calibration\.hdmi_mode_label/);
    expect(src).toMatch(/calibration\.audio_label/);
  });

  test("EN + DE locales carry the 8 calibration keys at parity (CAL-UI-04)", async () => {
    const en = (await import("@/locales/en.json")).default as unknown as Record<
      string,
      string
    >;
    const de = (await import("@/locales/de.json")).default as unknown as Record<
      string,
      string
    >;
    const keys = [
      "signage.admin.device.calibration.title",
      "signage.admin.device.calibration.rotation_label",
      "signage.admin.device.calibration.hdmi_mode_label",
      "signage.admin.device.calibration.hdmi_mode_auto",
      "signage.admin.device.calibration.audio_label",
      "signage.admin.device.calibration.audio_on",
      "signage.admin.device.calibration.audio_off",
      "signage.admin.device.calibration.saved",
    ];
    for (const k of keys) {
      expect(en[k], `EN missing: ${k}`).toBeTruthy();
      expect(de[k], `DE missing: ${k}`).toBeTruthy();
    }
    // Spot-check a few DE values differ from EN (du-tone translation, not
    // identity). "Audio" is legitimately identical across locales.
    expect(de["signage.admin.device.calibration.title"]).toBe("Kalibrierung");
    expect(de["signage.admin.device.calibration.rotation_label"]).toBe(
      "Drehung",
    );
    expect(de["signage.admin.device.calibration.saved"]).toBe(
      "Kalibrierung gespeichert",
    );
  });
});
