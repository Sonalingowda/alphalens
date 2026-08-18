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
      "/api/v1/opportunities": {
        contract_version: "1.0.0",
        data: {
          contract_version: "1.0.0",
          items: [
            {
              opportunity_id: "opportunity.1",
              opportunity_version_id: "opportunity.1.v1",
              scope: { instrument: "BTCUSDT", timeframe: "5m" },
              stance: "SELL",
              lifecycle_state: "PUBLISHED",
              evidence_cutoff: "2026-08-01T00:00:00Z",
              available_at: "2026-08-01T00:00:00Z",
              freshness_state: "CURRENT",
              rank: 1,
              reason_codes: ["ema.alignment"],
              score_reference: {
                artifact_id: "score.1",
                artifact_type: "score_result",
                artifact_version: "1.0.0",
                integrity_digest: "s".repeat(64),
                available_at: "2026-08-01T00:00:00Z",
              },
              has_plan: true,
              limitations: ["Confidence was not published."],
              detail_reference: "detail.1",
            },
          ],
          applied_filters: [],
          sort: "canonical.rank",
        },
        response_hash: "c".repeat(64),
      },
      "/api/v1/opportunities/opportunity.1": {
        contract_version: "1.0.0",
        data: {
          detail_id: "detail.1",
          opportunity: {
            opportunity_id: "opportunity.1",
            opportunity_version_id: "opportunity.1.v1",
            scope: { instrument: "BTCUSDT", timeframe: "5m" },
            stance: "SELL",
            available_at: "2026-08-01T00:00:00Z",
            reason_codes: ["ema.alignment"],
            limitations: ["Confidence was not published."],
            has_plan: true,
            plan: {
              contract_version: "1.0.0",
              plan_id: "plan.1",
              opportunity_id: "opportunity.1",
              assessment_id: "assessment.1",
              decision_id: "decision.1",
              policy: {
                policy_id: "policy.1",
                policy_version: "v1",
                integrity_digest: "a".repeat(64),
              },
              scope: { instrument: "BTCUSDT", timeframe: "5m" },
              direction: "SELL",
              reference_price: "63908.82",
              reference_price_source: {
                artifact_id: "market.1",
                artifact_type: "market_snapshot",
                artifact_version: "1.0.0",
                integrity_digest: "b".repeat(64),
                available_at: "2026-08-01T00:00:00Z",
              },
              entry_zone: { lower: "63908.82", upper: "63927.99" },
              entry_semantics: "Enter on confirmation.",
              invalidation_price: "63927.992646",
              invalidation_condition: "Invalidated on close above the threshold.",
              targets: [
                {
                  target_id: "tp.1",
                  price: "63880.061031",
                  potential_reward: "42.0",
                  risk_reward: "1.5",
                  evidence_references: [
                    {
                      artifact_id: "evidence.1",
                      artifact_type: "evidence_item",
                      artifact_version: "1.0.0",
                      integrity_digest: "c".repeat(64),
                      available_at: "2026-08-01T00:00:00Z",
                    },
                  ],
                },
                {
                  target_id: "tp.2",
                  price: "63852.000000",
                  potential_reward: "70.0",
                  risk_reward: "2.0",
                  evidence_references: [
                    {
                      artifact_id: "evidence.2",
                      artifact_type: "evidence_item",
                      artifact_version: "1.0.0",
                      integrity_digest: "d".repeat(64),
                      available_at: "2026-08-01T00:00:00Z",
                    },
                  ],
                },
                {
                  target_id: "tp.3",
                  price: "63820.000000",
                  potential_reward: "102.0",
                  risk_reward: "3.0",
                  evidence_references: [
                    {
                      artifact_id: "evidence.3",
                      artifact_type: "evidence_item",
                      artifact_version: "1.0.0",
                      integrity_digest: "e".repeat(64),
                      available_at: "2026-08-01T00:00:00Z",
                    },
                  ],
                },
              ],
              risk: "28.76",
              risk_unit: "points",
              assumptions: ["Trend continuation remains intact."],
              limitations: ["Order execution latency not modeled."],
              audit: {
                evidence_cutoff: "2026-08-01T00:00:00Z",
                available_at: "2026-08-01T00:00:00Z",
                result_hash: "d".repeat(64),
                provenance: {
                  source_references: [
                    {
                      artifact_id: "market.1",
                      artifact_type: "market_snapshot",
                      artifact_version: "1.0.0",
                      integrity_digest: "b".repeat(64),
                      available_at: "2026-08-01T00:00:00Z",
                    },
                  ],
                  policy_references: [
                    {
                      policy_id: "policy.1",
                      policy_version: "v1",
                      integrity_digest: "a".repeat(64),
                    },
                  ],
                  code_version: "frontend-test",
                  configuration_hash: "e".repeat(64),
                  lineage_hash: "f".repeat(64),
                },
              },
            },
            confidence: null,
            audit: {
              evidence_cutoff: "2026-08-01T00:00:00Z",
              available_at: "2026-08-01T00:00:00Z",
              result_hash: "e".repeat(64),
              provenance: {
                source_references: [
                  {
                    artifact_id: "market.1",
                    artifact_type: "market_snapshot",
                    artifact_version: "1.0.0",
                    integrity_digest: "b".repeat(64),
                    available_at: "2026-08-01T00:00:00Z",
                  },
                ],
                policy_references: [
                  {
                    policy_id: "policy.1",
                    policy_version: "v1",
                    integrity_digest: "a".repeat(64),
                  },
                ],
                code_version: "frontend-test",
                configuration_hash: "e".repeat(64),
                lineage_hash: "f".repeat(64),
              },
            },
          },
        },
        response_hash: "e".repeat(64),
      },
    };
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = new URL(String(input));
      return new Response(JSON.stringify(envelopeByPath[url.pathname]), { status: 200, headers: { "Content-Type": "application/json" } });
    });
    vi.stubGlobal("fetch", fetchMock);

    const element = await DashboardPage({ searchParams: Promise.resolve({}) });
    render(element as unknown as ReactElement);

    expect(screen.getByText("Opportunities")).toBeInTheDocument();
    expect(screen.getAllByText("BTCUSDT").length).toBeGreaterThan(0);
    expect(screen.getAllByText("SELL").length).toBeGreaterThan(0);
    expect(screen.getByText("ENTRY")).toBeInTheDocument();
    expect(screen.getByText("TARGET 1")).toBeInTheDocument();
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
        detail_id: "detail.1",
        opportunity: {
          opportunity_id: "opportunity.1",
          opportunity_version_id: "opportunity.1.v1",
          scope: { instrument: "BTCUSDT", timeframe: "5m" },
          stance: "BUY",
          detected_at: "2026-08-01T00:00:00Z",
          available_at: "2026-08-01T00:00:00Z",
          reason_codes: ["ema.alignment"],
          score_reference: {
            artifact_id: "score.1",
            artifact_type: "score_result",
            artifact_version: "1.0.0",
            integrity_digest: "s".repeat(64),
            available_at: "2026-08-01T00:00:00Z",
          },
          limitations: ["Confidence was not published."],
          has_plan: true,
          plan: {
            contract_version: "1.0.0",
            plan_id: "plan.1",
            opportunity_id: "opportunity.1",
            assessment_id: "assessment.1",
            decision_id: "decision.1",
            policy: {
              policy_id: "policy.1",
              policy_version: "v1",
              integrity_digest: "a".repeat(64),
            },
            scope: { instrument: "BTCUSDT", timeframe: "5m" },
            direction: "BUY",
            reference_price: "63908.82",
            reference_price_source: {
              artifact_id: "market.1",
              artifact_type: "market_snapshot",
              artifact_version: "1.0.0",
              integrity_digest: "b".repeat(64),
              available_at: "2026-08-01T00:00:00Z",
            },
            entry_zone: { lower: "63908.82", upper: "63927.99" },
            entry_semantics: "Enter on confirmation.",
            invalidation_price: "63927.992646",
            invalidation_condition: "Invalidated on close above the threshold.",
            targets: [
              {
                target_id: "tp.1",
                price: "63880.061031",
                potential_reward: "42.0",
                risk_reward: "1.5",
                evidence_references: [
                  {
                    artifact_id: "evidence.1",
                    artifact_type: "evidence_item",
                    artifact_version: "1.0.0",
                    integrity_digest: "c".repeat(64),
                    available_at: "2026-08-01T00:00:00Z",
                  },
                ],
              },
            ],
            risk: "28.76",
            risk_unit: "points",
            assumptions: ["Trend continuation remains intact."],
            limitations: ["Order execution latency not modeled."],
            audit: {
              evidence_cutoff: "2026-08-01T00:00:00Z",
              available_at: "2026-08-01T00:00:00Z",
              result_hash: "d".repeat(64),
              provenance: {
                source_references: [
                  {
                    artifact_id: "market.1",
                    artifact_type: "market_snapshot",
                    artifact_version: "1.0.0",
                    integrity_digest: "b".repeat(64),
                    available_at: "2026-08-01T00:00:00Z",
                  },
                ],
                policy_references: [
                  {
                    policy_id: "policy.1",
                    policy_version: "v1",
                    integrity_digest: "a".repeat(64),
                  },
                ],
                code_version: "frontend-test",
                configuration_hash: "e".repeat(64),
                lineage_hash: "f".repeat(64),
              },
            },
          },
          confidence: null,
          audit: {
            evidence_cutoff: "2026-08-01T00:00:00Z",
            available_at: "2026-08-01T00:00:00Z",
            result_hash: "e".repeat(64),
            provenance: {
              source_references: [
                {
                  artifact_id: "market.1",
                  artifact_type: "market_snapshot",
                  artifact_version: "1.0.0",
                  integrity_digest: "b".repeat(64),
                  available_at: "2026-08-01T00:00:00Z",
                },
              ],
              policy_references: [
                {
                  policy_id: "policy.1",
                  policy_version: "v1",
                  integrity_digest: "a".repeat(64),
                },
              ],
              code_version: "frontend-test",
              configuration_hash: "e".repeat(64),
              lineage_hash: "f".repeat(64),
            },
          },
        },
        market_snapshot: {
          contract_version: "1.0.0",
          snapshot_id: "market.1",
          scope: { instrument: "BTCUSDT", timeframe: "5m" },
          candles: [
            {
              candle_id: "candle.1",
              timestamp: "2026-08-01T00:00:00Z",
              available_at: "2026-08-01T00:05:00Z",
              open: "65000.0",
              high: "65100.0",
              low: "64900.0",
              close: "65050.0",
              volume: "12.5",
            },
          ],
          complete: true,
          audit: {
            created_at: "2026-08-01T00:05:00Z",
            evidence_cutoff: "2026-08-01T00:05:00Z",
            available_at: "2026-08-01T00:05:00Z",
            result_hash: "b".repeat(64),
          },
        },
        indicators: [],
        evidence: {
          package_id: "pkg.1",
          candidate_id: "opportunity.1",
          assessment_id: "assessment.1",
          items: [
            {
              taxonomy_version: "1.0.0",
              evidence_id: "evidence.1",
              evidence_type: "indicator",
              category: "trend",
              description_code: "ema.alignment",
              source_reference: {
                artifact_id: "market.1",
                artifact_type: "market_snapshot",
                artifact_version: "1.0.0",
                integrity_digest: "b".repeat(64),
                available_at: "2026-08-01T00:00:00Z",
              },
              source_definition: "EMA relationship",
              polarity: "positive",
              proposition: "Fast EMA is above slow EMA.",
              severity: "medium",
              observed_value: true,
              unit: null,
              scope: { instrument: "BTCUSDT", timeframe: "5m" },
              time_start: "2026-08-01T00:00:00Z",
              time_end: "2026-08-01T00:05:00Z",
              available_at: "2026-08-01T00:05:00Z",
              price_scope: { lower: "63900.0", upper: "63910.0" },
              limitations: [],
              integrity_digest: "c".repeat(64),
            },
          ],
          limitations: ["Evidence is point-in-time only."],
          audit: {
            evidence_cutoff: "2026-08-01T00:05:00Z",
            available_at: "2026-08-01T00:05:00Z",
            result_hash: "c".repeat(64),
            provenance: {
              source_references: [],
              policy_references: [],
              code_version: "frontend-test",
              configuration_hash: "e".repeat(64),
              lineage_hash: "f".repeat(64),
            },
          },
        },
        explanation: {
          contract_version: "1.0.0",
          explanation_id: "explanation.1",
          opportunity_version_id: "opportunity.1.v1",
          language: "en",
          locale: "en-US",
          taxonomy_version: "1.0.0",
          template_set_version: "1.0.0",
          sections: [
            {
              section_id: "section.1",
              ordinal: 1,
              sentences: [
                {
                  sentence_id: "sentence.1",
                  template_id: "template.1",
                  rendered_text: "EMA alignment supports the BUY stance.",
                  evidence_references: [
                    {
                      artifact_id: "evidence.1",
                      artifact_type: "evidence_item",
                      artifact_version: "1.0.0",
                      integrity_digest: "c".repeat(64),
                      available_at: "2026-08-01T00:05:00Z",
                    },
                  ],
                },
              ],
            },
          ],
          limitations: ["Render is derived from persisted sections."],
          audit: {
            evidence_cutoff: "2026-08-01T00:05:00Z",
            available_at: "2026-08-01T00:05:00Z",
            result_hash: "d".repeat(64),
            provenance: {
              source_references: [],
              policy_references: [],
              code_version: "frontend-test",
              configuration_hash: "e".repeat(64),
              lineage_hash: "f".repeat(64),
            },
          },
        },
        lifecycle: { current_state: "PUBLISHED", current_event_id: "event.1", events: [] },
        verification_status: "verified",
        audit: {
          evidence_cutoff: "2026-08-01T00:00:00Z",
          available_at: "2026-08-01T00:00:00Z",
          result_hash: "e".repeat(64),
          provenance: {
            source_references: [],
            policy_references: [],
            code_version: "frontend-test",
            configuration_hash: "e".repeat(64),
            lineage_hash: "f".repeat(64),
          },
        },
      },
      response_hash: "e".repeat(64),
    };
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = new URL(String(input));
      if (url.pathname.startsWith("/api/v1/opportunities/")) {
        return new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      return new Response(JSON.stringify({ contract_version: "1.0.0", data: {} }), { status: 200, headers: { "Content-Type": "application/json" } });
    });
    vi.stubGlobal("fetch", fetchMock);

    const element = await OpportunityDetailPage({
      params: Promise.resolve({ id: "opportunity.1" }),
      searchParams: Promise.resolve({ as_of: "2026-08-10T19:05:00.016000Z" }),
    });
    render(element as unknown as ReactElement);

    expect(screen.getByText("Opportunity detail")).toBeInTheDocument();
    expect(screen.getAllByText("Trade plan").length).toBeGreaterThan(0);
    expect(screen.getByText("Quality / score")).toBeInTheDocument();
    expect(screen.getByText("Reason codes")).toBeInTheDocument();
    expect(screen.getByText("score_result · 1.0.0")).toBeInTheDocument();
    expect(screen.getAllByText("ema.alignment").length).toBeGreaterThan(0);
    expect(screen.getAllByText("ema.alignment").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Entry").length).toBeGreaterThan(0);
    expect(screen.getAllByText("63908.82 - 63927.99").length).toBeGreaterThan(0);
    expect(screen.getAllByText("63927.992646").length).toBeGreaterThan(0);
    expect(screen.getAllByText("63880.061031").length).toBeGreaterThan(0);
    expect(screen.getAllByText("1.5").length).toBeGreaterThan(0);
    expect(screen.getByText("Verified")).toBeInTheDocument();
    expect(screen.getByText("Market snapshot")).toBeInTheDocument();
  });

  it("shows API unavailable when detail fetch fails", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("unavailable", { status: 503 })));
    const element = await OpportunityDetailPage({
      params: Promise.resolve({ id: "opportunity.1" }),
      searchParams: Promise.resolve({ as_of: "2026-08-10T19:05:00.016000Z" }),
    });
    render(element as unknown as ReactElement);
    expect(screen.getAllByText("Live Prediction API unavailable").length).toBeGreaterThan(0);
  });
});
