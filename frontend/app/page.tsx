import { Activity, Radar, ShieldCheck, TriangleAlert } from "lucide-react";

import { DashboardRail } from "@/components/dashboard/dashboard-rail";
import { HistoricalOpportunitiesTable } from "@/components/opportunities/historical-opportunities-table";
import { OpportunityFeed } from "@/components/opportunities/opportunity-feed";
import { ApiUnavailable } from "@/components/dashboard/data-states";
import { PageHeader } from "@/components/dashboard/page-header";
import { MetricCard } from "@/components/dashboard/metric-card";
import { Badge } from "@/components/ui/badge";
import { getLiveMarket, getLocalRuntimeStatus, getMvpHealth, getOpportunities, getOpportunityDetail } from "@/lib/api";
import type {
  OpportunityDashboardItem,
  OpportunityFilters as Filters,
  OpportunityPlan,
} from "@/lib/types";

type OpportunityEnrichment = {
  plan: OpportunityPlan | null;
  confidence: string | null;
  snr: string | null;
  quality: string | null;
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
  const [health, market, opportunities, runtime, history] = await Promise.all([
    getMvpHealth(),
    getLiveMarket(filters.instrument, filters.timeframe),
    getOpportunities(filters),
    getLocalRuntimeStatus(),
    getOpportunities(filters, undefined, "history"),
  ]);
  const { enrichments, partialFailures } = await loadOpportunityEnrichments(
    opportunities.ok ? opportunities.data.items : [],
  );
  const currentPrice = market.ok && market.data.candles.length
    ? market.data.candles.at(-1)?.close ?? null
    : null;

  return (
    <>
      <PageHeader
        eyebrow="Opportunity intelligence"
        title="Trading Opportunities"
        description="Verified opportunity records from completed market snapshots. AlphaLens informs; you make every trading decision."
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

      <div className="dashboard-layout">
        <main className="min-w-0 space-y-6">
        <section id="opportunities" className="scroll-mt-24 space-y-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.16em] text-primary">Primary feed</p>
            <h2 className="mt-1 text-xl font-semibold">Opportunities</h2>
          </div>
          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Opportunity summary">
          <MetricCard
            label="Active opportunities"
            value={opportunities.ok ? String(opportunities.data.items.length) : "Unavailable"}
            detail="Current filtered ranking projection"
            icon={Radar}
          />
          <MetricCard
            label="Market coverage"
            value={opportunities.ok ? formatCoverageStatus(opportunities.data.coverage_status) : "Unavailable"}
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
          {!opportunities.ok ? (
            <ApiUnavailable message={opportunities.error} />
          ) : (
            <OpportunityFeed
              filters={filters}
              initialItems={opportunities.data.items}
              initialEnrichments={enrichments}
              initialPartialFailures={Array.from(
                new Set([
                  ...(opportunities.data.partial_failures ?? []),
                  ...partialFailures,
                ]),
              )}
              currentPrice={currentPrice}
              initialView="active"
              initialFeedStatus={opportunities.data.feed_status}
            />
          )}
        </section>

        <section className="space-y-3" aria-label="Historical opportunities">
          <div className="flex flex-wrap items-end justify-between gap-2"><div><p className="text-xs font-medium uppercase tracking-[0.16em] text-primary">History</p><h2 className="mt-1 text-lg font-semibold">Recent Opportunities</h2></div><p className="text-xs text-muted-foreground">Immutable historical records</p></div>
          {history.ok ? <HistoricalOpportunitiesTable items={history.data.items} /> : <ApiUnavailable message={history.error} />}
        </section>
        </main>

        <DashboardRail
          runtime={runtime.ok ? runtime.data : null}
          market={market.ok ? market.data : null}
          items={[
            ...(opportunities.ok ? opportunities.data.items : []),
            ...(history.ok ? history.data.items : []),
          ]}
        />
      </div>
    </>
  );
}

function formatCoverageStatus(value: string | null | undefined): string {
  if (!value) return "Not reported";
  const labels: Record<string, string> = {
    thesis_primary_assessment_only: "Primary assessment only",
    complete: "Complete",
    partial: "Partial",
    unavailable: "Unavailable",
  };
  return labels[value] ?? "Reported status";
}

async function loadOpportunityEnrichments(
  items: OpportunityDashboardItem[],
): Promise<{
  enrichments: Map<string, OpportunityEnrichment>;
  partialFailures: string[];
}> {
  const partialFailures: string[] = [];
  const entries = await Promise.all(
    items.map(async (item) => {
      const quality = item.quality_score ?? null;

      if (item.projection_status === "assessment_only") {
        return [item.opportunity_id, {
          plan: item.plan ?? null,
          confidence: null,
          snr: null,
          quality,
        }] as const;
      }

      if (!item.has_plan) {
        return [item.opportunity_id, { plan: null, confidence: null, snr: null, quality }] as const;
      }

      const detailResult = await getOpportunityDetail(
        item.opportunity_id,
        item.available_at,
      );

      if (!detailResult.ok) {
        partialFailures.push(item.opportunity_id);
        return [item.opportunity_id, { plan: null, confidence: null, snr: null, quality }] as const;
      }

      const detail = detailResult.data;
      const plan = detail.opportunity.plan ?? null;
      const confidenceVal = detail.opportunity.confidence?.value ?? null;
      const confidence = confidenceVal
        ? `${confidenceVal}`
        : null;
      const snrVal = plan?.expected_move_confidence ?? null;
      const snr = snrVal ? `${snrVal}` : null;

      return [item.opportunity_id, { plan, confidence, snr, quality }] as const;
    }),
  );

  return { enrichments: new Map(entries), partialFailures };
}
