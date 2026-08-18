import { Activity, Radar, ShieldCheck, TriangleAlert } from "lucide-react";

import { MarketStatus } from "@/components/markets/market-status";
import { OpportunityCard } from "@/components/opportunities/opportunity-card";
import { OpportunityFilters } from "@/components/opportunities/opportunity-filters";
import { ApiUnavailable, EmptyState } from "@/components/dashboard/data-states";
import { PageHeader } from "@/components/dashboard/page-header";
import { MetricCard } from "@/components/dashboard/metric-card";
import { Badge } from "@/components/ui/badge";
import { getLiveMarket, getMvpHealth, getOpportunities, getOpportunityDetail } from "@/lib/api";
import type {
  OpportunityDashboardItem,
  OpportunityFilters as Filters,
  OpportunityPlan,
} from "@/lib/types";

type OpportunityEnrichment = {
  plan: OpportunityPlan | null;
  confidence: string | null;
};

type DashboardSearchParams = Promise<{
  instrument?: string;
  timeframe?: string;
  stance?: string;
  search?: string;
}>;

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: DashboardSearchParams;
}) {
  const requested = await searchParams;
  const filters: Filters = {
    instrument: requested.instrument || "BTCUSDT",
    timeframe: ["5m", "10m", "15m"].includes(requested.timeframe ?? "")
      ? requested.timeframe!
      : "5m",
    stance:
      requested.stance === "BUY" || requested.stance === "SELL"
        ? requested.stance
        : undefined,
    search: requested.search?.trim() || undefined,
  };
  const [health, market, opportunities] = await Promise.all([
    getMvpHealth(),
    getLiveMarket(filters.instrument, filters.timeframe),
    getOpportunities(filters),
  ]);
  const enrichments = await loadOpportunityEnrichments(
    opportunities.ok ? opportunities.data.items : [],
  );
  const currentPrice = market.ok && market.data.candles.length
    ? market.data.candles.at(-1)?.close ?? null
    : null;

  return (
    <>
      <PageHeader
        eyebrow="Opportunity intelligence"
        title="Market surveillance"
        description="Deterministic, evidence-backed opportunities from completed market snapshots. AlphaLens informs; you make every trading decision."
        actions={
          <Badge
            variant="outline"
            className={health.ok && health.data.status === "ready" ? "border-emerald-400/30 text-emerald-400" : "border-amber-400/30 text-amber-300"}
          >
            <span className={`mr-2 size-1.5 rounded-full ${health.ok && health.data.status === "ready" ? "bg-emerald-400" : "bg-amber-400"}`} />
            {health.ok ? `API ${health.data.status}` : "API unavailable"}
          </Badge>
        }
      />

      <div className="space-y-6">
        {market.ok ? <MarketStatus snapshot={market.data} /> : <ApiUnavailable message={market.error} />}

        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label="Active opportunities"
            value={opportunities.ok ? String(opportunities.data.items.length) : "Unavailable"}
            detail="Current filtered ranking projection"
            icon={Radar}
          />
          <MetricCard
            label="Market coverage"
            value={opportunities.ok ? opportunities.data.coverage_status ?? "Not reported" : "Unavailable"}
            detail={`${filters.instrument} · ${filters.timeframe}`}
            icon={Activity}
          />
          <MetricCard
            label="Data integrity"
            value={market.ok && market.data.complete ? "Complete" : "Unavailable"}
            detail="Immutable completed-candle snapshot"
            icon={ShieldCheck}
            tone={market.ok && market.data.complete ? "positive" : "default"}
          />
          <MetricCard
            label="Partial failures"
            value={opportunities.ok ? String(opportunities.data.partial_failures?.length ?? 0) : "Unavailable"}
            detail="Fail-closed projection issues"
            icon={TriangleAlert}
          />
        </section>

        <section id="opportunities" className="scroll-mt-24 space-y-4">
          <div className="flex flex-col justify-between gap-3 md:flex-row md:items-end">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.16em] text-primary">Ranked feed</p>
              <h2 className="mt-1 text-xl font-semibold">Opportunities</h2>
            </div>
            {opportunities.ok ? (
              <p className="font-mono text-[10px] text-muted-foreground">
                RESPONSE {opportunities.responseHash.slice(0, 12)}
              </p>
            ) : null}
          </div>
          <OpportunityFilters values={filters} />
          {!opportunities.ok ? (
            <ApiUnavailable message={opportunities.error} />
          ) : opportunities.data.items.length === 0 ? (
            <EmptyState
              title="No qualified opportunities"
              description="No immutable ranked opportunities match this scope. AlphaLens does not create placeholder signals."
            />
          ) : (
            <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
              {opportunities.data.items.map((item) => {
                const enrich = enrichments.get(item.opportunity_id);
                return (
                  <OpportunityCard
                    key={item.opportunity_id}
                    item={item}
                    plan={enrich?.plan ?? null}
                    currentPrice={currentPrice}
                    confidence={enrich?.confidence ?? null}
                  />
                );
              })}
            </div>
          )}
        </section>
      </div>
    </>
  );
}

async function loadOpportunityEnrichments(
  items: OpportunityDashboardItem[],
): Promise<Map<string, OpportunityEnrichment>> {
  const entries = await Promise.all(
    items.map(async (item) => {
      if (!item.has_plan) {
        return [item.opportunity_id, { plan: null, confidence: null }] as const;
      }

      const detailResult = await getOpportunityDetail(
        item.opportunity_id,
        item.available_at,
      );

      if (!detailResult.ok) {
        return [item.opportunity_id, { plan: null, confidence: null }] as const;
      }

      const detail = detailResult.data;
      const plan = detail.opportunity.plan ?? null;
      const confidenceVal = detail.opportunity.confidence?.value ?? null;
      const confidence = confidenceVal
        ? `${confidenceVal}`
        : null;

      return [item.opportunity_id, { plan, confidence }] as const;
    }),
  );

  return new Map(entries);
}
