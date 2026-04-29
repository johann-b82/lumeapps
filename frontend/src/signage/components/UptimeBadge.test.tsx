import { render } from "@testing-library/react";
import { describe, it, expect, beforeAll } from "vitest";
import { I18nextProvider } from "react-i18next";

import i18n, { i18nInitPromise } from "@/i18n";
import { UptimeBadge, uptimeTier } from "./UptimeBadge";
import type { SignageDeviceAnalytics } from "@/signage/lib/signageTypes";

beforeAll(async () => {
  await i18nInitPromise;
  await i18n.changeLanguage("en");
});

const wrap = (ui: React.ReactElement) =>
  render(<I18nextProvider i18n={i18n}>{ui}</I18nextProvider>);

const mk = (overrides: Partial<SignageDeviceAnalytics> = {}): SignageDeviceAnalytics => ({
  device_id: "d1",
  uptime_24h_pct: 100,
  missed_windows_24h: 0,
  window_minutes: 1440,
  ...overrides,
});

describe("uptimeTier", () => {
  it("maps null → neutral", () => {
    expect(uptimeTier(null)).toBe("neutral");
  });
  it("maps ≥95 → green", () => {
    expect(uptimeTier(100)).toBe("green");
    expect(uptimeTier(95)).toBe("green");
  });
  it("maps just below 95 → amber", () => {
    expect(uptimeTier(94.9)).toBe("amber");
  });
  it("maps 80..94.9 → amber", () => {
    expect(uptimeTier(80)).toBe("amber");
    expect(uptimeTier(90)).toBe("amber");
  });
  it("maps <80 → red", () => {
    expect(uptimeTier(79.9)).toBe("red");
    expect(uptimeTier(0)).toBe("red");
  });
});

describe("<UptimeBadge />", () => {
  it("renders neutral '—' for undefined data", () => {
    const { container } = wrap(<UptimeBadge variant="uptime" data={undefined} />);
    expect(container.textContent).toContain("—");
    expect(container.innerHTML).toMatch(/bg-muted/);
    const span = container.querySelector("span[title]");
    expect(span?.getAttribute("title")).toContain("No heartbeats");
  });

  it("renders neutral '—' when uptime_24h_pct is null (zero-heartbeat case)", () => {
    const { container } = wrap(
      <UptimeBadge
        variant="uptime"
        data={mk({ uptime_24h_pct: null, missed_windows_24h: 0, window_minutes: 0 })}
      />,
    );
    expect(container.textContent).toContain("—");
    expect(container.innerHTML).toMatch(/bg-muted/);
  });

  it("renders green for 95%", () => {
    const { container } = wrap(
      <UptimeBadge
        variant="uptime"
        data={mk({ uptime_24h_pct: 95.0, missed_windows_24h: 72, window_minutes: 1440 })}
      />,
    );
    expect(container.innerHTML).toMatch(/bg-green-100/);
    expect(container.textContent).toContain("95.0%");
  });

  it("renders amber for 94.9%", () => {
    const { container } = wrap(
      <UptimeBadge
        variant="uptime"
        data={mk({ uptime_24h_pct: 94.9, missed_windows_24h: 74, window_minutes: 1440 })}
      />,
    );
    expect(container.innerHTML).toMatch(/bg-amber-100/);
    expect(container.innerHTML).not.toMatch(/bg-green-100/);
  });

  it("renders red for 79.9%", () => {
    const { container } = wrap(
      <UptimeBadge
        variant="uptime"
        data={mk({ uptime_24h_pct: 79.9, missed_windows_24h: 290, window_minutes: 1440 })}
      />,
    );
    expect(container.innerHTML).toMatch(/bg-red-100/);
  });

  it("missed variant inherits row tier (red for 50% uptime)", () => {
    const { container } = wrap(
      <UptimeBadge
        variant="missed"
        data={mk({ uptime_24h_pct: 50.0, missed_windows_24h: 720, window_minutes: 1440 })}
      />,
    );
    expect(container.textContent).toContain("720");
    expect(container.innerHTML).toMatch(/bg-red-100/);
    const span = container.querySelector("span[title]");
    expect(span?.getAttribute("title")).toContain("720");
    expect(span?.getAttribute("title")).toContain("one-minute windows");
  });

  it("partial-window uses tooltip_partial with windowH=Math.ceil(30/60)=1", () => {
    const { container } = wrap(
      <UptimeBadge
        variant="uptime"
        data={mk({ uptime_24h_pct: 100.0, missed_windows_24h: 0, window_minutes: 30 })}
      />,
    );
    expect(container.innerHTML).toMatch(/bg-green-100/);
    const span = container.querySelector("span[title]");
    const title = span?.getAttribute("title") ?? "";
    expect(title).toContain("30");
    expect(title).toContain("1 h");
    expect(title).toContain("device is new");
  });

  it("full-window tooltip contains buckets / denom numbers", () => {
    const { container } = wrap(
      <UptimeBadge
        variant="uptime"
        data={mk({ uptime_24h_pct: 95.0, missed_windows_24h: 72, window_minutes: 1440 })}
      />,
    );
    const span = container.querySelector("span[title]");
    const title = span?.getAttribute("title") ?? "";
    expect(title).toContain("1368");
    expect(title).toContain("1440");
    expect(title).toContain("had a heartbeat in the last 24 h");
  });

  it("DE locale yields DE tooltip copy", async () => {
    await i18n.changeLanguage("de");
    const { container } = wrap(
      <UptimeBadge
        variant="uptime"
        data={mk({ uptime_24h_pct: 95.0, missed_windows_24h: 72, window_minutes: 1440 })}
      />,
    );
    const span = container.querySelector("span[title]");
    const title = span?.getAttribute("title") ?? "";
    expect(title).toContain("Heartbeat");
    expect(title).toContain("Ein-Minuten-Fenster");
    await i18n.changeLanguage("en");
  });
});
