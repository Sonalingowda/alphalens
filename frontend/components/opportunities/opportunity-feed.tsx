"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { TriangleAlert } from "lucide-react";

import { OpportunityCard } from "@/components/opportunities/opportunity-card";
import { ApiUnavailable, EmptyState } from "@/components/dashboard/data-states";
import { fetchOpportunities } from "@/lib/api-client";
import type {
  OpportunityDashboardItem,
  OpportunityFilters,
  OpportunityPlan,
} from "@/lib/types";

type Enrichment = {
  plan: OpportunityPlan | null;
  confidence: string | null;
  snr: string | null;
  quality: string | null;
};

const POLL_INTERVAL_MS = 15_000;
const FAILURE_THRESHOLD = 3;

export function OpportunityFeed({
  filters,
  initialItems,
  initialEnrichments,
  initialPartialFailures,
  currentPrice,
}: {
  filters: OpportunityFilters;
  initialItems: OpportunityDashboardItem[];
  initialEnrichments: Map<string, Enrichment>;
  initialPartialFailures?: string[];
  currentPrice: string | null;
}) {
  const [items, setItems] = useState<OpportunityDashboardItem[]>(initialItems);
  const [enrichments, setEnrichments] = useState<Map<string, Enrichment>>(initialEnrichments);
  const [partialFailureCount, setPartialFailureCount] = useState(
    initialPartialFailures?.length ?? 0,
  );
  const [error, setError] = useState<string | null>(null);
  const [failureCount, setFailureCount] = useState(0);
  const enrichmentsRef = useRef(enrichments);

  useEffect(() => {
    enrichmentsRef.current = enrichments;
  }, [enrichments]);

  const poll = useCallback(async () => {
    const result = await fetchOpportunities(filters);
    if (!result.ok) {
      setFailureCount((count) => count + 1);
      setError(result.error);
      return;
    }
    setFailureCount(0);
    setError(null);
    setItems(result.data.items);
    setPartialFailureCount(result.data.partial_failures?.length ?? 0);

    const existing = enrichmentsRef.current;
    const newEnrichments = new Map<string, Enrichment>();
    for (const item of result.data.items) {
      const cached = existing.get(item.opportunity_id);
      if (cached) {
        newEnrichments.set(item.opportunity_id, cached);
      }
    }
    setEnrichments(newEnrichments);
  }, [filters]);

  useEffect(() => {
    const id = setInterval(poll, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [poll]);

  if (error !== null && (failureCount >= FAILURE_THRESHOLD || items.length === 0)) {
    return <ApiUnavailable message={error} />;
  }

  const cardsGrid = (
    <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
      {items.map((item) => {
        const enrich = enrichments.get(item.opportunity_id);
        return (
          <OpportunityCard
            key={item.opportunity_id}
            item={item}
            plan={enrich?.plan ?? null}
            currentPrice={currentPrice}
            snr={enrich?.snr ?? null}
            quality={enrich?.quality ?? null}
          />
        );
      })}
    </div>
  );

  if (error !== null) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2 rounded-lg border border-amber-500/25 bg-amber-500/5 px-4 py-3 text-sm text-amber-300">
          <TriangleAlert className="size-4 shrink-0" aria-hidden="true" />
          <span>
            Backend reconnecting — showing the last successfully fetched
            snapshot. Next attempt in ≤15s.
          </span>
          <span className="ml-auto font-mono text-[10px]">{error}</span>
        </div>
        {cardsGrid}
      </div>
    );
  }

  const partialFailureNotice = partialFailureCount > 0 ? (
    <div className="flex items-center gap-2 rounded-lg border border-amber-500/25 bg-amber-500/5 px-4 py-3 text-sm text-amber-300">
      <TriangleAlert className="size-4 shrink-0" aria-hidden="true" />
      <span>
        {partialFailureCount} opportunity {partialFailureCount === 1 ? "detail is" : "details are"} unavailable. Persisted summaries remain visible; retry to load the missing detail.
      </span>
      <button
        type="button"
        className="ml-auto shrink-0 rounded border border-amber-400/40 px-2 py-1 text-xs hover:bg-amber-400/10"
        onClick={() => window.location.reload()}
      >
        Retry details
      </button>
    </div>
  ) : null;

  if (items.length === 0) {
    return (
      <EmptyState
        title="No qualified opportunities"
        description="No immutable ranked opportunities match this scope. AlphaLens does not create placeholder signals."
      />
    );
  }

  return partialFailureNotice ? (
    <div className="space-y-4">
      {partialFailureNotice}
      {cardsGrid}
    </div>
  ) : cardsGrid;
}
