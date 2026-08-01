import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getDashboardBundle,
  getLiveMarket,
  getMvpHealth,
  getOpportunities,
  getOpportunityDetail,
} from "@/lib/api";

const dashboard = {
  snapshot_version: "1.0.0",
  generated_at: "2026-07-30T00:00:00+00:00",
  prediction: null,
  signal: null,
  confidence: { available: false, reason: "Not produced." },
  portfolio: {
    available: false,
    cash: null,
    portfolio_value: null,
    daily_pnl: null,
    unrealized_pnl: null,
    realized_pnl: null,
    open_position_count: 0,
    closed_trade_count: 0,
  },
  predictions: [],
  signals: [],
  orders: [],
  trades: [],
  risk_events: [],
  portfolio_history: [],
  charts: {
    equity_curve: [],
    daily_returns: [],
    drawdown: [],
    prediction_history: [],
    trade_timeline: [],
    position_history: [],
  },
  backtest_reports: [],
  system: {
    api_version: "1.0.0",
    database_status: "connected",
    model_family: "ridge_regression",
    model_version: "1.0.0",
    artifact_identifier: "artifact",
    artifact_sha256: "a".repeat(64),
    artifact_configuration_hash: "b".repeat(64),
    feature_pipeline_version: "1.1.0",
    target_version: "1.0.0",
    paper_engine_version: null,
    risk_framework_version: null,
    test_status: "not_published_by_runtime",
  },
  settings: null,
  provenance: {
    paper_report_id: null,
    paper_result_hash: null,
    risk_report_id: null,
    risk_result_hash: null,
    backtest_report_ids: [],
    inference_artifact_id: "artifact",
  },
};

const health = {
  status: "healthy",
  api_version: "1.0.0",
  artifact_status: "verified",
  artifact_identifier: "artifact",
  read_only: true,
};

const model = {
  api_version: "1.0.0",
  artifact_identifier: "artifact",
  model_family: "ridge_regression",
  artifact_version: "1.0.0",
  artifact_sha256: "a".repeat(64),
  configuration_hash: "b".repeat(64),
  feature_pipeline_version: "1.1.0",
  target_version: "1.0.0",
  target_name: "forward_log_return",
  horizon_observations: 5,
  schema_hash: "c".repeat(64),
  feature_count: 12,
  ordered_feature_names: [],
};

const metrics = {
  api_version: "1.0.0",
  request_count: 4,
  successful_request_count: 4,
  error_request_count: 0,
  prediction_count: 1,
  average_latency_microseconds: 100,
  maximum_latency_microseconds: 200,
  health: "operational",
};

const resources = {
  api_version: "1.0.0",
  uptime_seconds: 3600,
  process_cpu_user_seconds: 12.5,
  process_cpu_system_seconds: 2.1,
  maximum_resident_set_bytes: 268435456,
};

describe("Live Prediction API integration", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads the complete read-only dashboard bundle", async () => {
    const payloads: Record<string, unknown> = {
      "/api/v1/dashboard": dashboard,
      "/api/v1/health": health,
      "/api/v1/model": model,
      "/api/v1/metrics": metrics,
      "/api/v1/resources": resources,
    };
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = new URL(String(input));
      return new Response(JSON.stringify(payloads[url.pathname]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await getDashboardBundle();

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.health.status).toBe("healthy");
      expect(result.data.model.model_family).toBe("ridge_regression");
      expect(result.data.dashboard.system.database_status).toBe("connected");
      expect(result.data.metrics.request_count).toBe(4);
      expect(result.data.resources.uptime_seconds).toBe(3600);
    }
    expect(fetchMock).toHaveBeenCalledTimes(5);
  });

  it("fails closed when any required API projection is unavailable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("unavailable", { status: 503 })),
    );

    const result = await getDashboardBundle();

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toContain("503");
    }
  });
});

describe("AlphaLens MVP API integration", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads deterministic market, opportunity, detail, and health envelopes", async () => {
    const envelopeByPath: Record<string, unknown> = {
      "/health": {
        contract_version: "1.0.0",
        data: {
          status: "ready",
          service: "alphalens-mvp-api",
          api_version: "1.0.0",
          read_only: true,
          authentication_required: false,
          components: {
            market_snapshots: "configured",
            opportunity_dashboard: "configured",
            opportunity_detail: "configured",
          },
        },
        response_hash: "a".repeat(64),
      },
      "/markets/live": {
        contract_version: "1.0.0",
        data: {
          contract_version: "1.0.0",
          snapshot_id: "market.1",
          scope: { instrument: "BTCUSDT", timeframe: "5m" },
          candles: [],
          complete: true,
          audit: {
            created_at: "2026-08-01T00:00:00Z",
            evidence_cutoff: "2026-08-01T00:00:00Z",
            available_at: "2026-08-01T00:00:00Z",
            result_hash: "b".repeat(64),
          },
        },
        response_hash: "b".repeat(64),
      },
      "/opportunities": {
        contract_version: "1.0.0",
        data: {
          contract_version: "1.0.0",
          items: [],
          applied_filters: [],
          sort: "canonical.rank",
        },
        response_hash: "c".repeat(64),
      },
      "/opportunities/opportunity.1": {
        contract_version: "1.0.0",
        data: { contract_version: "1.0.0", detail_id: "detail.1" },
        response_hash: "d".repeat(64),
      },
    };
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = new URL(String(input));
      return new Response(JSON.stringify(envelopeByPath[url.pathname]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const [healthResult, marketResult, opportunityResult, detailResult] =
      await Promise.all([
        getMvpHealth(),
        getLiveMarket(),
        getOpportunities({ instrument: "BTCUSDT", timeframe: "5m" }),
        getOpportunityDetail("opportunity.1"),
      ]);

    expect(healthResult.ok && healthResult.data.status).toBe("ready");
    expect(marketResult.ok && marketResult.data.snapshot_id).toBe("market.1");
    expect(opportunityResult.ok && opportunityResult.data.items).toEqual([]);
    expect(detailResult.ok && detailResult.data.detail_id).toBe("detail.1");
    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain("timeframe=5m");
  });

  it("returns an explicit unavailable state instead of placeholder data", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("unavailable", { status: 503 })),
    );

    const result = await getLiveMarket();

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toContain("503");
  });
});
