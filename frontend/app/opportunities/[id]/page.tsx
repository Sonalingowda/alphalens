import { ArrowLeft, CheckCircle2, Clock3, Database, Gauge } from "lucide-react";
import Link from "next/link";

import { ApiUnavailable, EmptyState } from "@/components/dashboard/data-states";
import { PageHeader } from "@/components/dashboard/page-header";
import { MarketCandlestickChart } from "@/components/markets/market-candlestick-chart";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getOpportunityDetail } from "@/lib/api";
import { formatNumber, formatTimestamp, shortHash, titleCase } from "@/lib/format";

export default async function OpportunityDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const result = await getOpportunityDetail(id);

  if (!result.ok) {
    return (
      <>
        <PageHeader eyebrow="Opportunity detail" title="Opportunity unavailable" description="The requested immutable opportunity projection could not be loaded." />
        <ApiUnavailable message={result.error} />
      </>
    );
  }

  const detail = result.data;
  const opportunity = detail.opportunity;
  const explanation = extractExplanation(detail.explanation);
  return (
    <>
      <PageHeader
        eyebrow="Opportunity detail"
        title={`${opportunity.scope.instrument} · ${opportunity.stance}`}
        description={`Immutable ${opportunity.scope.timeframe} opportunity with complete evidence, lifecycle, and audit references.`}
        actions={<Button variant="outline" size="sm" render={<Link href="/" />}><ArrowLeft className="size-4" />Back to feed</Button>}
      />
      <div className="space-y-6">
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Fact icon={Gauge} label="Lifecycle" value={titleCase(detail.lifecycle.current_state ?? "Not reported")} />
          <Fact icon={Clock3} label="Evidence cutoff" value={formatTimestamp(detail.audit.evidence_cutoff)} />
          <Fact icon={CheckCircle2} label="Verification" value={titleCase(detail.verification_status)} />
          <Fact icon={Database} label="Result hash" value={shortHash(detail.audit.result_hash)} mono />
        </section>

        <section className="grid gap-4 xl:grid-cols-[1.4fr_.6fr]">
          <Card className="bg-card/95">
            <CardHeader><CardTitle>Market snapshot</CardTitle><CardDescription>Point-in-time candles attached to this opportunity.</CardDescription></CardHeader>
            <CardContent><MarketCandlestickChart candles={detail.market_snapshot.candles} /></CardContent>
          </Card>
          <Card className="bg-card/95">
            <CardHeader><CardTitle>Explanation</CardTitle><CardDescription>Deterministically generated from stored evidence.</CardDescription></CardHeader>
            <CardContent>
              {explanation.length ? (
                <div className="space-y-3">{explanation.map((line) => <p key={line} className="text-sm leading-6 text-muted-foreground">{line}</p>)}</div>
              ) : (
                <EmptyState title="No explanation text" description="The detail projection does not contain a human-readable explanation." />
              )}
            </CardContent>
          </Card>
        </section>

        <Card className="bg-card/95">
          <CardHeader><CardTitle>Approved indicators</CardTitle><CardDescription>Values are shown exactly as persisted; no client-side calculations are performed.</CardDescription></CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {detail.indicators.map((indicator) => (
              <div key={`${indicator.feature_identifier}:${indicator.output_name}`} className="rounded-lg border bg-muted/20 p-4">
                <div className="mb-3 flex items-center justify-between gap-2"><span className="font-mono text-xs font-medium">{indicator.feature_identifier}</span><Badge variant="outline">{indicator.definition_version}</Badge></div>
                <p className="text-xl font-semibold tabular">{formatNumber(indicator.value, 6)}</p>
                <p className="mt-1 text-xs text-muted-foreground">{indicator.output_name} · {indicator.unit}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function Fact({ icon: Icon, label, value, mono = false }: { icon: typeof Gauge; label: string; value: string; mono?: boolean }) {
  return <Card className="bg-card/95"><CardContent className="flex items-center gap-3 p-5"><span className="grid size-9 place-items-center rounded-lg border bg-muted/30"><Icon className="size-4 text-primary" /></span><div className="min-w-0"><p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">{label}</p><p className={`mt-1 truncate text-sm font-medium ${mono ? "font-mono" : ""}`}>{value}</p></div></CardContent></Card>;
}

function extractExplanation(value: Record<string, unknown>): string[] {
  const candidates = [value.summary, value.text, value.narrative, value.sentences];
  for (const candidate of candidates) {
    if (typeof candidate === "string" && candidate.trim()) return [candidate];
    if (Array.isArray(candidate) && candidate.every((item) => typeof item === "string")) return candidate;
  }
  return [];
}
