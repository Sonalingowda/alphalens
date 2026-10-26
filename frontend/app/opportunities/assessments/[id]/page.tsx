import Link from "next/link";

import { ApiUnavailable, EmptyState } from "@/components/dashboard/data-states";
import { PageHeader } from "@/components/dashboard/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getAssessmentDetail } from "@/lib/api";
import { formatTimestamp } from "@/lib/format";
import { EconomicAnalysis } from "@/components/opportunities/economic-analysis";

export default async function AssessmentDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ as_of?: string }>;
}) {
  const { id } = await params;
  const { as_of: asOf } = await searchParams;
  const result = await getAssessmentDetail(id, asOf);

  if (!result.ok) {
    return (
      <>
        <PageHeader
          eyebrow="Assessment detail"
          title="Assessment unavailable"
          description="The persisted assessment could not be loaded."
        />
        <ApiUnavailable message={result.error} />
      </>
    );
  }

  const { opportunity } = result.data;
  const plan = opportunity.plan;

  return (
    <>
      <PageHeader
        eyebrow="Assessment detail"
        title={`${opportunity.scope.instrument} · ${opportunity.stance}`}
        description="Genuine persisted Detection/Assessment output. This record is not ranked and has no approved model score."
        actions={<Button nativeButton={false} variant="outline" size="sm" render={<Link href="/" />}>Back to feed</Button>}
      />
      <div className="space-y-6">
        <div className="rounded-xl border border-amber-400/25 bg-amber-400/5 p-4 text-sm text-amber-200">
          Assessment-only projection: model scoring is unavailable without an approved BTCUSDT/5m artifact; no confidence or notification delivery is implied.
        </div>
        <section className="grid gap-4 md:grid-cols-3">
          <Fact label="Projection" value="Assessment only" />
          <Fact label="Available" value={formatTimestamp(opportunity.available_at ?? "")} />
          <Fact label="Lifecycle" value="Not created before ranking" />
        </section>
        <Card>
          <CardHeader><CardTitle>Genuine persisted trade plan</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            {plan ? (
              <div className="grid gap-3 sm:grid-cols-2">
                <Fact label="Direction" value={plan.direction} />
                <Fact label="Entry" value={`${plan.entry_zone.lower} – ${plan.entry_zone.upper}`} />
                <Fact label="Invalidation" value={plan.invalidation_price} />
                <Fact label="Target 1" value={plan.targets[0]?.price ?? "Unavailable"} />
                <Fact label="Risk / Reward" value={plan.targets[0]?.risk_reward ?? "Unavailable"} />
                <Fact label="Model output" value="Unavailable" />
              </div>
            ) : <EmptyState title="Plan unavailable" description="No persisted plan was attached to this assessment." />}
          </CardContent>
        </Card>
        {plan ? (
          <EconomicAnalysis
            opportunityId={opportunity.opportunity_id}
            asOf={asOf ?? opportunity.available_at}
            direction={plan.direction}
          />
        ) : null}
        <Card>
          <CardHeader><CardTitle>Provenance</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <p>Candidate: <span className="font-mono">{opportunity.candidate_id}</span></p>
            <p>Assessment: <span className="font-mono">{opportunity.assessment_id}</span></p>
            <p>Evidence cutoff: {formatTimestamp(opportunity.audit?.evidence_cutoff ?? "")}</p>
            <Badge variant="outline">No ranking or model score</Badge>
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border bg-muted/20 p-3">
      <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">{label}</p>
      <p className="mt-1 font-mono text-sm">{value}</p>
    </div>
  );
}
