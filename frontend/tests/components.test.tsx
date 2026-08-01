import { render, screen } from "@testing-library/react";
import { TrendingUp } from "lucide-react";
import { describe, expect, it } from "vitest";

import { ApiUnavailable, EmptyState } from "@/components/dashboard/data-states";
import { MetricCard } from "@/components/dashboard/metric-card";
import { SignalBadge } from "@/components/dashboard/signal-badge";
import { MarketStatus } from "@/components/markets/market-status";
import { OpportunityCard } from "@/components/opportunities/opportunity-card";

describe("dashboard presentation components", () => {
  it("renders an evidence-backed metric without transforming it", () => {
    render(
      <MetricCard
        label="Current prediction"
        value="2.308%"
        detail="5-observation forward log return"
        icon={TrendingUp}
      />,
    );

    expect(screen.getByText("Current prediction")).toBeInTheDocument();
    expect(screen.getByText("2.308%")).toBeInTheDocument();
    expect(
      screen.getByText("5-observation forward log return"),
    ).toBeInTheDocument();
  });

  it.each(["BUY", "HOLD", "EXIT"] as const)(
    "renders the %s signal exactly",
    (action) => {
      render(<SignalBadge action={action} />);
      expect(screen.getByText(action)).toBeInTheDocument();
    },
  );

  it("makes unavailable data explicit", () => {
    render(<ApiUnavailable message="Connection refused." />);
    expect(
      screen.getByText("Live Prediction API unavailable"),
    ).toBeInTheDocument();
    expect(screen.getByText("Connection refused.")).toBeInTheDocument();
  });

  it("renders an honest empty state", () => {
    render(
      <EmptyState
        title="No closed trades"
        description="No immutable trade evidence is available."
      />,
    );
    expect(screen.getByText("No closed trades")).toBeInTheDocument();
  });
});

describe("MVP market intelligence components", () => {
  it("renders an opportunity from the immutable projection", () => {
    render(
      <OpportunityCard
        item={{
          opportunity_id: "opportunity.1",
          opportunity_version_id: "opportunity.1.v1",
          scope: { instrument: "BTCUSDT", timeframe: "15m" },
          stance: "BUY",
          lifecycle_state: "PUBLISHED",
          evidence_cutoff: "2026-08-01T00:00:00Z",
          available_at: "2026-08-01T00:00:00Z",
          freshness_state: "CURRENT",
          rank: 1,
          reason_codes: ["ema.alignment"],
          has_plan: false,
          limitations: ["Confidence policy is not approved."],
          detail_reference: "detail.1",
        }}
      />,
    );

    expect(screen.getByText("BTCUSDT")).toBeInTheDocument();
    expect(screen.getAllByText("BUY").length).toBeGreaterThan(0);
    expect(screen.getByText("ema.alignment")).toBeInTheDocument();
    expect(screen.getByText("Confidence policy is not approved.")).toBeInTheDocument();
  });

  it("renders market values exactly from the API snapshot", () => {
    render(
      <MarketStatus
        snapshot={{
          contract_version: "1.0.0",
          snapshot_id: "market.BTCUSDT.5m.1",
          scope: { instrument: "BTCUSDT", timeframe: "5m" },
          complete: true,
          candles: [
            {
              candle_id: "candle.1",
              timestamp: "2026-08-01T00:00:00Z",
              available_at: "2026-08-01T00:05:00Z",
              open: "65000.000000000000000000",
              high: "65100.000000000000000000",
              low: "64900.000000000000000000",
              close: "65050.000000000000000000",
              volume: "12.500000000000000000",
            },
          ],
          audit: {
            created_at: "2026-08-01T00:05:00Z",
            evidence_cutoff: "2026-08-01T00:05:00Z",
            available_at: "2026-08-01T00:05:00Z",
            result_hash: "a".repeat(64),
          },
        }}
      />,
    );

    expect(screen.getByText("$65,050.00")).toBeInTheDocument();
    expect(screen.getByText("BTCUSDT · 5m")).toBeInTheDocument();
    expect(screen.getByText("UTC normalized")).toBeInTheDocument();
  });
});
