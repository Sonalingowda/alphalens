"use client";

import { useCallback, useEffect, useRef, useState } from "react";

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
};

const POLL_INTERVAL_MS = 15_000;

export function OpportunityFeed({
  filters,
  initialItems,
  initialEnrichments,
  currentPrice,
}: {
  filters: OpportunityFilters;
  initialItems: OpportunityDashboardItem[];
  initialEnrichments: Map<string, Enrichment>;
  currentPrice: string | null;
}) {
  const [items, setItems] = useState<OpportunityDashboardItem[]>(initialItems);
  const [enrichments, setEnrichments] = useState<Map<string, Enrichment>>(initialEnrichments);
  const [error, setError] = useState<string | null>(null);
  const enrichmentsRef = useRef(enrichments);
  enrichmentsRef.current = enrichments;

  const poll = useCallback(async () => {
    const result = await fetchOpportunities(filters);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    setError(null);
    setItems(result.data.items);

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

  if (error) {
    return <ApiUnavailable message={error} />;
  }

  if (items.length === 0) {
    return (
      <EmptyState
        title="No qualified opportunities"
        description="No immutable ranked opportunities match this scope. AlphaLens does not create placeholder signals."
      />
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
      {items.map((item) => {
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
  );
}
