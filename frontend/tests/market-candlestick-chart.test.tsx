import { render, screen, waitFor, cleanup } from "@testing-library/react";
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

import { MarketCandlestickChart } from "@/components/markets/market-candlestick-chart";

describe("MarketCandlestickChart loading behavior", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });
  it("shows a skeleton when no candles are provided", () => {
    render(<MarketCandlestickChart candles={[]} />);
    const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders chart container when candles are provided", async () => {
    render(
      <MarketCandlestickChart
        candles={[{
          candle_id: "c1",
          timestamp: "2026-08-01T00:00:00Z",
          available_at: "2026-08-01T00:05:00Z",
          open: "65000",
          high: "65100",
          low: "64900",
          close: "65050",
          volume: "1",
        }]}
      />,
    );
    // The skeleton should be removed once the chart initializes.
    await waitFor(() => {
      expect(document.querySelectorAll('[data-slot="skeleton"]').length).toBe(0);
    });
    expect(screen.getByLabelText("BTCUSDT candlestick chart")).toBeInTheDocument();
  });
});
