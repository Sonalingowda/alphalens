import { render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { describe, expect, it, vi, afterEach } from "vitest";

vi.mock("lightweight-charts", () => ({
  createChart: (_el: Element) => {
    void _el;
    return {
      addSeries: () => ({ setData: () => {} }),
      timeScale: () => ({ fitContent: () => {} }),
      remove: () => {},
    };
  },
  CandlestickSeries: {},
  ColorType: { Solid: 0 },
}));

import DashboardPage from "@/app/page";
import LiveMarketPage from "@/app/markets/live/page";
import OpportunityDetailPage from "@/app/opportunities/[id]/page";

describe("Page integration: Dashboard", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders successful dashboard snapshot", async () => {
    const envelopeByPath: Record<string, unknown> = {
      "/health": { contract_version: "1.0.0", data: { status: "ready", data: {} }, response_hash: "a".repeat(64) },
      "/markets/live": { contract_version: "1.0.0", data: { snapshot_id: "market.1", scope: { instrument: "BTCUSDT", timeframe: "5m" }, candles: [], complete: true, audit: { created_at: "2026-08-01T00:00:00Z", evidence_cutoff: "2026-08-01T00:00:00Z", available_at: "2026-08-01T00:00:00Z", result_hash: "b".repeat(64) } }, response_hash: "b".repeat(64) },
      "/opportunities": { contract_version: "1.0.0", data: { items: [] }, response_hash: "c".repeat(64) },
    };
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = new URL(String(input));
      return new Response(JSON.stringify(envelopeByPath[url.pathname]), { status: 200, headers: { "Content-Type": "application/json" } });
    });
    vi.stubGlobal("fetch", fetchMock);

    const element = await DashboardPage({ searchParams: Promise.resolve({}) });
    render(element as unknown as ReactElement);

    expect(screen.getByText("Opportunities")).toBeInTheDocument();
  });

  it("shows API unavailable state when fetch fails", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("unavailable", { status: 503 })));

    const element = await DashboardPage({ searchParams: Promise.resolve({}) });
    render(element as unknown as ReactElement);

    expect(screen.getAllByText("Live Prediction API unavailable").length).toBeGreaterThan(0);
  });
});

describe("Page integration: Markets", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders empty candles state", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = new URL(String(input));
      if (url.pathname === "/markets/live") {
        return new Response(JSON.stringify({ contract_version: "1.0.0", data: { snapshot_id: "m1", scope: { instrument: "BTCUSDT", timeframe: "5m" }, candles: [], complete: true, audit: { created_at: "2026-08-01T00:00:00Z", evidence_cutoff: "2026-08-01T00:00:00Z", available_at: "2026-08-01T00:00:00Z", result_hash: "d".repeat(64) } } , response_hash: "d".repeat(64) }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      return new Response(JSON.stringify({ contract_version: "1.0.0", data: {} }), { status: 200, headers: { "Content-Type": "application/json" } });
    });
    vi.stubGlobal("fetch", fetchMock);

    const element = await LiveMarketPage({ searchParams: Promise.resolve({}) });
    render(element as unknown as ReactElement);

    expect(screen.getByText("No completed candles")).toBeInTheDocument();
  });

  it("shows API unavailable for markets", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("unavailable", { status: 503 })));
    const element = await LiveMarketPage({ searchParams: Promise.resolve({}) });
    render(element as unknown as ReactElement);
    expect(screen.getAllByText("Live Prediction API unavailable").length).toBeGreaterThan(0);
  });
});

describe("Page integration: Opportunity detail", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders opportunity detail successfully", async () => {
    const payload = {
      contract_version: "1.0.0",
      data: {
        opportunity: { scope: { instrument: "BTCUSDT", timeframe: "5m" }, stance: "BUY" },
        market_snapshot: { candles: [] },
        audit: { evidence_cutoff: "2026-08-01T00:00:00Z", result_hash: "e".repeat(64) },
        indicators: [],
        explanation: { text: "Reasoning" },
        lifecycle: { current_state: "PUBLISHED" },
        verification_status: "verified",
      },
      response_hash: "e".repeat(64),
    };
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = new URL(String(input));
      if (url.pathname.startsWith("/opportunities/")) {
        return new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      return new Response(JSON.stringify({ contract_version: "1.0.0", data: {} }), { status: 200, headers: { "Content-Type": "application/json" } });
    });
    vi.stubGlobal("fetch", fetchMock);

    const element = await OpportunityDetailPage({ params: Promise.resolve({ id: "opportunity.1" }) });
    render(element as unknown as ReactElement);

    expect(screen.getByText("Opportunity detail")).toBeInTheDocument();
    expect(screen.getByText("Market snapshot")).toBeInTheDocument();
  });

  it("shows API unavailable when detail fetch fails", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("unavailable", { status: 503 })));
    const element = await OpportunityDetailPage({ params: Promise.resolve({ id: "opportunity.1" }) });
    render(element as unknown as ReactElement);
    expect(screen.getAllByText("Live Prediction API unavailable").length).toBeGreaterThan(0);
  });
});
