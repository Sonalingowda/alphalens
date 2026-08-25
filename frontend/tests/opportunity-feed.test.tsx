import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OpportunityFeed } from "@/components/opportunities/opportunity-feed";
import type { OpportunityDashboardItem } from "@/lib/types";

const POLL_INTERVAL_MS = 15_000;
const FAILURE_THRESHOLD = 3;

function makeItem(
  overrides: Partial<OpportunityDashboardItem> = {},
): OpportunityDashboardItem {
  return {
    opportunity_id: "opportunity.test.a",
    opportunity_version_id: "opportunity.test.a.v1",
    scope: { instrument: "BTCUSDT", timeframe: "5m" },
    stance: "SELL",
    lifecycle_state: "PUBLISHED",
    evidence_cutoff: "2026-08-01T00:00:00Z",
    available_at: "2026-08-01T00:00:00Z",
    freshness_state: "CURRENT",
    rank: 1,
    reason_codes: ["ema.alignment"],
    has_plan: false,
    limitations: [],
    detail_reference: "detail.test.a",
    ...overrides,
  };
}

function envelope(data: unknown): Response {
  return new Response(
    JSON.stringify({
      contract_version: "1.0.0",
      data,
      response_hash: "c".repeat(64),
    }),
    { status: 200, headers: { "Content-Type": "application/json" } },
  );
}

function opportunityPage(items: OpportunityDashboardItem[]): Response {
  return envelope({ contract_version: "1.0.0", items });
}

type PollStep = () => Promise<Response>;

const timeoutFailure: PollStep = async () => {
  throw new Error("The operation was aborted due to timeout.");
};

function success(items: OpportunityDashboardItem[]): PollStep {
  return async () => opportunityPage(items);
}

let script: PollStep[];

beforeEach(() => {
  vi.useFakeTimers();
  script = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      const step = script.shift();
      if (!step) throw new Error("unexpected fetch call");
      return step();
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function advanceOnePoll(): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS);
  });
}

describe("OpportunityFeed transient failure handling", () => {
  it("keeps last-good cards with a reconnecting notice on the first failed poll", async () => {
    script = [timeoutFailure];

    render(
      <OpportunityFeed
        filters={{ instrument: "BTCUSDT", timeframe: "5m" }}
        initialItems={[makeItem()]}
        initialEnrichments={new Map()}
        currentPrice={null}
      />,
    );

    expect(screen.getByText("SELL")).toBeInTheDocument();

    await advanceOnePoll();

    expect(screen.getByText(/Backend reconnecting/)).toBeInTheDocument();
    expect(
      screen.getByText("The operation was aborted due to timeout."),
    ).toBeInTheDocument();
    expect(screen.getByText("SELL")).toBeInTheDocument();
    expect(
      screen.queryByText("Live Prediction API unavailable"),
    ).not.toBeInTheDocument();
  });

  it("shows ApiUnavailable with the raw message after three consecutive failures", async () => {
    script = [timeoutFailure, timeoutFailure, timeoutFailure];

    render(
      <OpportunityFeed
        filters={{ instrument: "BTCUSDT", timeframe: "5m" }}
        initialItems={[makeItem()]}
        initialEnrichments={new Map()}
        currentPrice={null}
      />,
    );

    for (let index = 0; index < FAILURE_THRESHOLD; index += 1) {
      await advanceOnePoll();
    }

    expect(screen.getByText("Live Prediction API unavailable")).toBeInTheDocument();
    expect(
      screen.getByText("The operation was aborted due to timeout."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Backend reconnecting/)).not.toBeInTheDocument();
  });

  it("recovers after a successful poll, refreshes items, and resets the failure counter", async () => {
    const refreshed = makeItem({
      opportunity_id: "opportunity.test.b",
      stance: "BUY",
      rank: 2,
    });
    script = [timeoutFailure, success([refreshed]), timeoutFailure];

    render(
      <OpportunityFeed
        filters={{ instrument: "BTCUSDT", timeframe: "5m" }}
        initialItems={[makeItem()]}
        initialEnrichments={new Map()}
        currentPrice={null}
      />,
    );

    await advanceOnePoll();
    expect(screen.getByText(/Backend reconnecting/)).toBeInTheDocument();
    expect(screen.getByText("SELL")).toBeInTheDocument();

    await advanceOnePoll();
    expect(screen.queryByText(/Backend reconnecting/)).not.toBeInTheDocument();
    expect(screen.getByText("BUY")).toBeInTheDocument();
    expect(screen.queryByText("SELL")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Live Prediction API unavailable"),
    ).not.toBeInTheDocument();

    await advanceOnePoll();
    expect(screen.getByText(/Backend reconnecting/)).toBeInTheDocument();
    expect(
      screen.queryByText("Live Prediction API unavailable"),
    ).not.toBeInTheDocument();
  });

  it("fails closed immediately when there are no last-good items", async () => {
    script = [timeoutFailure];

    render(
      <OpportunityFeed
        filters={{ instrument: "BTCUSDT", timeframe: "5m" }}
        initialItems={[]}
        initialEnrichments={new Map()}
        currentPrice={null}
      />,
    );

    await advanceOnePoll();

    expect(screen.getByText("Live Prediction API unavailable")).toBeInTheDocument();
    expect(screen.queryByText(/Backend reconnecting/)).not.toBeInTheDocument();
  });
});
