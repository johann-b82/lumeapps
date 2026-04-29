import { describe, it, expect, beforeEach, beforeAll, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";

import i18n, { i18nInitPromise } from "@/i18n";
import { DevicesPage } from "./DevicesPage";

vi.mock("@/signage/lib/signageApi", () => ({
  signageApi: {
    listDevices: vi.fn(),
    listDeviceAnalytics: vi.fn(),
    getResolvedForDevice: vi.fn(async (id: string) => ({
      current_playlist_id: null,
      current_playlist_name: null,
      tag_ids: null,
      _id: id,
    })),
    revokeDevice: vi.fn(),
    updateDevice: vi.fn(),
    replaceDeviceTags: vi.fn(),
    listTags: vi.fn(async () => []),
  },
  ApiErrorWithBody: class ApiErrorWithBody extends Error {
    status = 0;
    body: unknown = null;
  },
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("wouter", () => ({
  useLocation: () => ["/signage/devices", vi.fn()],
}));

import { signageApi } from "@/signage/lib/signageApi";

const mkDevice = (overrides = {}) => ({
  id: "d1",
  name: "Lobby Screen",
  status: "online" as const,
  last_seen_at: new Date().toISOString(),
  revoked_at: null,
  tags: [],
  tag_ids: [],
  current_playlist_id: null,
  current_playlist_name: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  ...overrides,
});

function renderPage(qc?: QueryClient) {
  const client =
    qc ??
    new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
  return {
    qc: client,
    ...render(
      <QueryClientProvider client={client}>
        <I18nextProvider i18n={i18n}>
          <DevicesPage />
        </I18nextProvider>
      </QueryClientProvider>,
    ),
  };
}

beforeAll(async () => {
  await i18nInitPromise;
});

describe("Phase 53 analytics columns", () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    await i18n.changeLanguage("en");
  });

  it("renders Uptime 24h and Missed 24h column headers", async () => {
    (signageApi.listDevices as unknown as ReturnType<typeof vi.fn>).mockResolvedValue([
      mkDevice(),
    ]);
    (
      signageApi.listDeviceAnalytics as unknown as ReturnType<typeof vi.fn>
    ).mockResolvedValue([
      {
        device_id: "d1",
        uptime_24h_pct: 95.0,
        missed_windows_24h: 72,
        window_minutes: 1440,
      },
    ]);
    renderPage();
    expect(await screen.findByText(/Uptime 24h/)).toBeInTheDocument();
    expect(await screen.findByText(/Missed 24h/)).toBeInTheDocument();
  });

  it("column order: Status appears before Uptime 24h, which appears before Missed 24h, which appears before Last seen", async () => {
    (signageApi.listDevices as unknown as ReturnType<typeof vi.fn>).mockResolvedValue([
      mkDevice(),
    ]);
    (
      signageApi.listDeviceAnalytics as unknown as ReturnType<typeof vi.fn>
    ).mockResolvedValue([
      {
        device_id: "d1",
        uptime_24h_pct: 100,
        missed_windows_24h: 0,
        window_minutes: 1440,
      },
    ]);
    const { container } = renderPage();
    await screen.findByText(/Uptime 24h/);
    const headers = Array.from(
      container.querySelectorAll("thead th"),
    ).map((th) => th.textContent ?? "");
    const idxStatus = headers.findIndex((h) => /Status/.test(h));
    const idxUptime = headers.findIndex((h) => /Uptime 24h/.test(h));
    const idxMissed = headers.findIndex((h) => /Missed 24h/.test(h));
    const idxLastSeen = headers.findIndex((h) => /Last seen/i.test(h));
    expect(idxStatus).toBeGreaterThanOrEqual(0);
    expect(idxUptime).toBe(idxStatus + 1);
    expect(idxMissed).toBe(idxStatus + 2);
    expect(idxLastSeen).toBeGreaterThan(idxMissed);
  });

  it("95% uptime renders a green badge", async () => {
    (signageApi.listDevices as unknown as ReturnType<typeof vi.fn>).mockResolvedValue([
      mkDevice(),
    ]);
    (
      signageApi.listDeviceAnalytics as unknown as ReturnType<typeof vi.fn>
    ).mockResolvedValue([
      {
        device_id: "d1",
        uptime_24h_pct: 95.0,
        missed_windows_24h: 72,
        window_minutes: 1440,
      },
    ]);
    const { container } = renderPage();
    await screen.findByText("95.0%");
    expect(container.innerHTML).toMatch(/bg-green-100/);
  });

  it("94.9% renders amber (not green)", async () => {
    (signageApi.listDevices as unknown as ReturnType<typeof vi.fn>).mockResolvedValue([
      mkDevice(),
    ]);
    (
      signageApi.listDeviceAnalytics as unknown as ReturnType<typeof vi.fn>
    ).mockResolvedValue([
      {
        device_id: "d1",
        uptime_24h_pct: 94.9,
        missed_windows_24h: 74,
        window_minutes: 1440,
      },
    ]);
    const { container } = renderPage();
    await screen.findByText("94.9%");
    // Tbody row only (avoid DeviceStatusChip's own green/amber in the same row —
    // but at 94.9% and recent last_seen_at, DeviceStatusChip is also green/amber).
    const tbody = container.querySelector("tbody")!;
    expect(tbody.innerHTML).toMatch(/bg-amber-100/);
  });

  it("79.9% renders red", async () => {
    (signageApi.listDevices as unknown as ReturnType<typeof vi.fn>).mockResolvedValue([
      mkDevice(),
    ]);
    (
      signageApi.listDeviceAnalytics as unknown as ReturnType<typeof vi.fn>
    ).mockResolvedValue([
      {
        device_id: "d1",
        uptime_24h_pct: 79.9,
        missed_windows_24h: 290,
        window_minutes: 1440,
      },
    ]);
    const { container } = renderPage();
    await screen.findByText("79.9%");
    expect(container.innerHTML).toMatch(/bg-red-100/);
  });

  it("device missing from analytics response renders neutral '—'", async () => {
    (signageApi.listDevices as unknown as ReturnType<typeof vi.fn>).mockResolvedValue([
      mkDevice({ id: "d1" }),
    ]);
    (
      signageApi.listDeviceAnalytics as unknown as ReturnType<typeof vi.fn>
    ).mockResolvedValue([]);
    const { container } = renderPage();
    // Wait for both queries to settle
    await screen.findByText(/Uptime 24h/);
    await waitFor(() => {
      const tbody = container.querySelector("tbody")!;
      expect(tbody.textContent).toContain("—");
      expect(tbody.innerHTML).toMatch(/bg-muted/);
    });
  });

  it("zero-heartbeat device (uptime_24h_pct: null) renders neutral '—'", async () => {
    (signageApi.listDevices as unknown as ReturnType<typeof vi.fn>).mockResolvedValue([
      mkDevice({ id: "d1" }),
    ]);
    (
      signageApi.listDeviceAnalytics as unknown as ReturnType<typeof vi.fn>
    ).mockResolvedValue([
      {
        device_id: "d1",
        uptime_24h_pct: null,
        missed_windows_24h: 0,
        window_minutes: 0,
      },
    ]);
    const { container } = renderPage();
    await screen.findByText(/Uptime 24h/);
    await waitFor(() => {
      const tbody = container.querySelector("tbody")!;
      expect(tbody.textContent).toContain("—");
      expect(tbody.innerHTML).toMatch(/bg-muted/);
    });
  });

  it("tooltip contains literal numerator/denominator in EN", async () => {
    (signageApi.listDevices as unknown as ReturnType<typeof vi.fn>).mockResolvedValue([
      mkDevice(),
    ]);
    (
      signageApi.listDeviceAnalytics as unknown as ReturnType<typeof vi.fn>
    ).mockResolvedValue([
      {
        device_id: "d1",
        uptime_24h_pct: 95.0,
        missed_windows_24h: 72,
        window_minutes: 1440,
      },
    ]);
    const { container } = renderPage();
    await screen.findByText("95.0%");
    const spans = Array.from(
      container.querySelectorAll("tbody span[title]"),
    ) as HTMLElement[];
    const uptimeSpan = spans.find((s) =>
      (s.getAttribute("title") ?? "").includes("had a heartbeat"),
    );
    expect(uptimeSpan).toBeDefined();
    const title = uptimeSpan!.getAttribute("title") ?? "";
    expect(title).toContain("1368");
    expect(title).toContain("1440");
    expect(title).toContain("had a heartbeat in the last 24 h");
  });

  it("tooltip switches to DE copy when i18n changes to de", async () => {
    await i18n.changeLanguage("de");
    (signageApi.listDevices as unknown as ReturnType<typeof vi.fn>).mockResolvedValue([
      mkDevice(),
    ]);
    (
      signageApi.listDeviceAnalytics as unknown as ReturnType<typeof vi.fn>
    ).mockResolvedValue([
      {
        device_id: "d1",
        uptime_24h_pct: 95.0,
        missed_windows_24h: 72,
        window_minutes: 1440,
      },
    ]);
    const { container } = renderPage();
    await screen.findByText("95.0%");
    const spans = Array.from(
      container.querySelectorAll("tbody span[title]"),
    ) as HTMLElement[];
    const deSpan = spans.find((s) =>
      (s.getAttribute("title") ?? "").includes("Ein-Minuten-Fenster"),
    );
    expect(deSpan).toBeDefined();
    const title = deSpan!.getAttribute("title") ?? "";
    expect(title).toContain("Heartbeat");
    expect(title).toContain("Ein-Minuten-Fenster");
    await i18n.changeLanguage("en");
  });

  it("partial-window 30-minute device shows tooltip_partial with windowH=1", async () => {
    (signageApi.listDevices as unknown as ReturnType<typeof vi.fn>).mockResolvedValue([
      mkDevice(),
    ]);
    (
      signageApi.listDeviceAnalytics as unknown as ReturnType<typeof vi.fn>
    ).mockResolvedValue([
      {
        device_id: "d1",
        uptime_24h_pct: 100.0,
        missed_windows_24h: 0,
        window_minutes: 30,
      },
    ]);
    const { container } = renderPage();
    await screen.findByText("100.0%");
    const spans = Array.from(
      container.querySelectorAll("tbody span[title]"),
    ) as HTMLElement[];
    const partialSpan = spans.find((s) =>
      (s.getAttribute("title") ?? "").includes("device is new"),
    );
    expect(partialSpan).toBeDefined();
    const title = partialSpan!.getAttribute("title") ?? "";
    expect(title).toContain("30");
    expect(title).toContain("1 h");
  });

  it("analytics query uses refetchOnWindowFocus: true", async () => {
    (signageApi.listDevices as unknown as ReturnType<typeof vi.fn>).mockResolvedValue([
      mkDevice(),
    ]);
    (
      signageApi.listDeviceAnalytics as unknown as ReturnType<typeof vi.fn>
    ).mockResolvedValue([
      {
        device_id: "d1",
        uptime_24h_pct: 95.0,
        missed_windows_24h: 72,
        window_minutes: 1440,
      },
    ]);
    const { qc } = renderPage();
    await waitFor(() => {
      const q = qc
        .getQueryCache()
        .find({ queryKey: ["fastapi", "analytics", "devices"] });
      expect(q).toBeDefined();
    });
    const q = qc
      .getQueryCache()
      .find({ queryKey: ["fastapi", "analytics", "devices"] })!;
    // TanStack Query stores observer options; poke every observer attached.
    const observers = q.observers ?? [];
    const hasFocusRefetch = observers.some(
      (o: { options: { refetchOnWindowFocus?: unknown } }) =>
        o.options.refetchOnWindowFocus === true,
    );
    expect(hasFocusRefetch).toBe(true);
  });
});

// Silence the "within" import warning — used in potential future assertions.
void within;
