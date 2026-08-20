import { ArrowLeft, CheckCircle2, Clock3, Database, Gauge, BadgeInfo, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { ApiUnavailable, EmptyState } from "@/components/dashboard/data-states";
import { PageHeader } from "@/components/dashboard/page-header";
import { MarketCandlestickChart } from "@/components/markets/market-candlestick-chart";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { getOpportunityDetail } from "@/lib/api";
import {
  formatNumber,
  formatTimestamp,
  shortHash,
  titleCase,
} from "@/lib/format";
import type { ExplanationArtifact } from "@/lib/types";

export default async function OpportunityDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ as_of?: string }>;
}) {
  const { id } = await params;
  const { as_of: asOf } = await searchParams;
  const result = await getOpportunityDetail(id, asOf);

  if (!result.ok) {
    return (
      <>
        <PageHeader
          eyebrow="Opportunity detail"
          title="Opportunity unavailable"
          description="The requested immutable opportunity projection could not be loaded."
        />
        <ApiUnavailable message={result.error} />
      </>
    );
  }

  const detail = result.data;
  const opportunity = detail.opportunity;
  const plan = opportunity.plan ?? null;
  const hasPlan = opportunity.has_plan && plan !== null;
  const confidence = opportunity.confidence ?? null;
  const reasonCodes = opportunity.reason_codes ?? [];
  const scoreReference = opportunity.score_reference ?? null;
  const explanation = extractExplanation(detail.explanation);
  const planTargets = plan?.targets ?? [];
  const evidenceItems = detail.evidence.items ?? [];
  const provenance =
    detail.audit.provenance ?? {
      source_references: [],
      policy_references: [],
      code_version: "Unavailable",
      configuration_hash: "",
      lineage_hash: "",
    };

  return (
    <>
      <PageHeader
        eyebrow="Opportunity detail"
        title={`${opportunity.scope.instrument} · ${opportunity.stance}`}
        description={`Immutable ${opportunity.scope.timeframe} opportunity with persisted plan, evidence, lifecycle, and audit references.`}
        actions={
          <Button variant="outline" size="sm" render={<Link href="/" />}>
            <ArrowLeft className="size-4" />
            Back to feed
          </Button>
        }
      />

      <div className="space-y-6">
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <Fact
            icon={Gauge}
            label="Lifecycle"
            value={titleCase(detail.lifecycle.current_state ?? "Unavailable")}
          />
          <Fact
            icon={CheckCircle2}
            label="Verification"
            value={titleCase(detail.verification_status)}
          />
          <Fact
            icon={Clock3}
            label="Freshness"
            value={formatTimestamp(opportunity.available_at ?? detail.audit.available_at)}
            detail="UTC availability"
          />
          <Fact
            icon={BadgeInfo}
            label="Evidence cutoff"
            value={formatTimestamp(detail.audit.evidence_cutoff)}
            detail="Point-in-time response cutoff"
          />
          <Fact
            icon={ShieldCheck}
            label="Confidence"
            value={confidence ? formatNumber(confidence.value, 2) : "Unavailable"}
            detail={
              confidence
                ? confidence.meaning
                : "No confidence record was published for this opportunity."
            }
          />
          <Fact
            icon={Gauge}
            label="SNR"
            value={
              plan?.expected_move_confidence
                ? `${Number(plan.expected_move_confidence).toFixed(2)}x`
                : "Unavailable"
            }
            detail={
              plan?.expected_move_confidence
                ? "Signal-to-noise ratio from expected-move model"
                : "No expected-move model output available for this opportunity."
            }
          />
          <Fact
            icon={Database}
            label="Result hash"
            value={shortHash(detail.audit.result_hash)}
            mono
          />
        </section>

        <section className="grid gap-4 xl:grid-cols-2">
          <Card className="bg-card/95">
            <CardHeader>
              <CardTitle>Quality / score</CardTitle>
              <CardDescription>
                Persisted score reference returned by the opportunity detail API.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <PlanFact
                label="Score reference"
                value={
                  scoreReference
                    ? shortHash(scoreReference.artifact_id)
                    : "Unavailable"
                }
                mono
              />
              <p className="text-sm text-muted-foreground">
                {scoreReference
                  ? `${scoreReference.artifact_type} · ${scoreReference.artifact_version}`
                  : "No score reference was published for this opportunity."}
              </p>
            </CardContent>
          </Card>

          <Card className="bg-card/95">
            <CardHeader>
              <CardTitle>Reason codes</CardTitle>
              <CardDescription>
                Evidence-backed assessment reasons returned by the backend.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {reasonCodes.length ? (
                <div className="flex flex-wrap gap-2">
                  {reasonCodes.map((code) => (
                    <Badge key={code} variant="outline" className="font-mono text-[10px]">
                      {code}
                    </Badge>
                  ))}
                </div>
              ) : (
                <EmptyState
                  title="No reason codes"
                  description="The backend did not publish assessment reason codes for this opportunity."
                />
              )}
            </CardContent>
          </Card>
        </section>

        <section className="grid gap-4 xl:grid-cols-[1.1fr_.9fr]">
          <Card className="bg-card/95">
            <CardHeader>
              <CardTitle>Market snapshot</CardTitle>
              <CardDescription>
                Point-in-time candles attached to this opportunity.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <MarketCandlestickChart candles={detail.market_snapshot.candles} />
            </CardContent>
          </Card>

          <Card className="bg-card/95">
            <CardHeader>
              <CardTitle>Trade plan</CardTitle>
              <CardDescription>
                Hydrated directly from the stored OpportunityPlan, if one exists.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              {hasPlan ? (
                <>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="secondary" className="font-mono text-[10px]">
                      {plan.direction}
                    </Badge>
                    <Badge variant="outline" className="font-mono text-[10px]">
                      {plan.scope.instrument}
                    </Badge>
                    <Badge variant="outline" className="font-mono text-[10px]">
                      {plan.scope.timeframe}
                    </Badge>
                    <Badge variant="outline" className="font-mono text-[10px]">
                      {plan.policy.policy_id}@{plan.policy.policy_version}
                    </Badge>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <PlanFact
                      label="Direction"
                      value={plan.direction}
                      mono
                    />
                    <PlanFact
                      label="Entry"
                      value={formatPlanRange(plan.entry_zone.lower, plan.entry_zone.upper)}
                      mono
                    />
                    <PlanFact
                      label="Stop / Invalidation"
                      value={displayPlanValue(plan.invalidation_price)}
                      mono
                    />
                    <PlanFact
                      label="Target 1"
                      value={displayPlanValue(plan.targets[0]?.price)}
                      mono
                    />
                    <PlanFact
                      label="Target 2"
                      value={displayPlanValue(plan.targets[1]?.price)}
                      mono
                    />
                    <PlanFact
                      label="Risk / Reward"
                      value={displayPlanValue(plan.targets[0]?.risk_reward)}
                      mono
                    />
                  </div>

                  <div className="rounded-xl border bg-muted/20 p-4">
                    <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
                      Targets
                    </p>
                    {planTargets.length ? (
                      <div className="mt-3 space-y-3">
                        {planTargets.map((target, index) => (
                          <div
                            key={target.target_id}
                            className="rounded-lg border bg-background/60 p-3"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="font-mono text-xs font-medium">
                                Target {index + 1}
                              </p>
                              <p className="font-mono text-xs text-muted-foreground">
                                {target.target_id}
                              </p>
                            </div>
                            <div className="mt-2 grid gap-2 text-sm sm:grid-cols-3">
                              <PlanFact label="Price" value={displayPlanValue(target.price)} />
                              <PlanFact
                                label="Potential reward"
                                value={displayPlanValue(target.potential_reward)}
                              />
                              <PlanFact
                                label="Risk / Reward"
                                value={displayPlanValue(target.risk_reward)}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="mt-2 text-sm text-muted-foreground">
                        No stored targets were published with this plan.
                      </p>
                    )}
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <ListCard title="Assumptions" values={plan.assumptions} />
                    <ListCard title="Limitations" values={plan.limitations} />
                  </div>
                </>
              ) : (
                <EmptyState
                  title="Plan unavailable"
                  description="This opportunity was published without a stored OpportunityPlan."
                />
              )}
            </CardContent>
          </Card>
        </section>

        <section className="grid gap-4 xl:grid-cols-[.95fr_1.05fr]">
          <Card className="bg-card/95">
            <CardHeader>
              <CardTitle>Evidence</CardTitle>
              <CardDescription>
                Stored evidence package and the items used to support the opportunity.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-xl border bg-muted/20 p-4">
                <div className="grid gap-3 sm:grid-cols-2">
                  <PlanFact label="Package" value={detail.evidence.package_id} mono />
                  <PlanFact label="Evidence items" value={String(evidenceItems.length)} />
                  <PlanFact
                    label="Candidate"
                    value={detail.evidence.candidate_id ?? "Unavailable"}
                    mono
                  />
                  <PlanFact
                    label="Assessment"
                    value={detail.evidence.assessment_id ?? "Unavailable"}
                    mono
                  />
                </div>
              </div>

              {evidenceItems.length ? (
                <div className="space-y-3">
                  {evidenceItems.slice(0, 4).map((item) => (
                    <div key={item.evidence_id} className="rounded-lg border p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="font-mono text-xs font-medium">
                          {item.description_code}
                        </p>
                        <Badge variant="outline" className="font-mono text-[10px]">
                          {item.category}
                        </Badge>
                      </div>
                      <p className="mt-2 text-sm leading-6 text-muted-foreground">
                        {String(item.proposition)}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2 text-[10px] text-muted-foreground">
                        <span>{String(item.observed_value)}</span>
                        {item.unit ? <span>Unit {item.unit}</span> : null}
                        <span>{formatTimestamp(item.available_at)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState
                  title="No evidence items"
                  description="The evidence package did not include item-level support in this response."
                />
              )}
            </CardContent>
          </Card>

          <Card className="bg-card/95">
            <CardHeader>
              <CardTitle>Explanation</CardTitle>
              <CardDescription>
                Human-readable explanation text rendered from persisted sections.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {explanation.length ? (
                <div className="space-y-3">
                  {explanation.map((line) => (
                    <p key={line} className="text-sm leading-6 text-muted-foreground">
                      {line}
                    </p>
                  ))}
                </div>
              ) : (
                <EmptyState
                  title="No explanation text"
                  description="The detail projection does not contain a rendered explanation."
                />
              )}
              <div className="grid gap-3 sm:grid-cols-2">
                <PlanFact label="Explanation ID" value={detail.explanation.explanation_id} mono />
                <PlanFact
                  label="Template set"
                  value={detail.explanation.template_set_version}
                />
                <PlanFact
                  label="Sections"
                  value={String(detail.explanation.sections.length)}
                />
                <PlanFact
                  label="Limitations"
                  value={String(detail.explanation.limitations.length)}
                />
              </div>
            </CardContent>
          </Card>
        </section>

        <Card className="bg-card/95">
          <CardHeader>
            <CardTitle>Audit provenance</CardTitle>
            <CardDescription>
              The UI only shows persisted provenance that came from the API response.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <PlanFact label="Code version" value={provenance.code_version} mono />
            <PlanFact
              label="Configuration hash"
              value={shortHash(provenance.configuration_hash)}
              mono
            />
            <PlanFact label="Lineage hash" value={shortHash(provenance.lineage_hash)} mono />
            <PlanFact
              label="Source refs"
              value={String(provenance.source_references.length)}
            />
            <PlanFact
              label="Policy refs"
              value={String(provenance.policy_references.length)}
            />
            <PlanFact
              label="Opportunity hash"
              value={shortHash(opportunity.audit?.result_hash ?? detail.audit.result_hash)}
              mono
            />
            <div className="md:col-span-2 xl:col-span-2">
              <ReferencesPanel
                label="Source references"
                values={provenance.source_references.map(
                  (reference) =>
                    `${reference.artifact_type}:${reference.artifact_id}`,
                )}
              />
            </div>
            <div className="md:col-span-2 xl:col-span-2">
              <ReferencesPanel
                label="Policy references"
                values={provenance.policy_references.map(
                  (reference) =>
                    `${reference.policy_id}@${reference.policy_version}`,
                )}
              />
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function Fact({
  icon: Icon,
  label,
  value,
  detail,
  mono = false,
}: {
  icon: typeof Gauge;
  label: string;
  value: string;
  detail?: string;
  mono?: boolean;
}) {
  return (
    <Card className="bg-card/95">
      <CardContent className="flex items-center gap-3 p-5">
        <span className="grid size-9 place-items-center rounded-lg border bg-muted/30">
          <Icon className="size-4 text-primary" />
        </span>
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
            {label}
          </p>
          <p className={`mt-1 truncate text-sm font-medium ${mono ? "font-mono" : ""}`}>
            {value}
          </p>
          {detail ? <p className="mt-1 text-xs text-muted-foreground">{detail}</p> : null}
        </div>
      </CardContent>
    </Card>
  );
}

function PlanFact({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="rounded-lg border bg-background/60 p-3">
      <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
        {label}
      </p>
      <p className={`mt-1 text-sm font-medium ${mono ? "font-mono" : ""}`}>{value}</p>
    </div>
  );
}

function ListCard({
  title,
  values,
}: {
  title: string;
  values: string[];
}) {
  return (
    <div className="rounded-xl border bg-muted/20 p-4">
      <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
        {title}
      </p>
      {values.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {values.map((value) => (
            <Badge key={value} variant="outline" className="max-w-full text-[10px]">
              <span className="truncate">{value}</span>
            </Badge>
          ))}
        </div>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">No persisted entries.</p>
      )}
    </div>
  );
}

function ReferencesPanel({
  label,
  values,
}: {
  label: string;
  values: string[];
}) {
  return (
    <div className="rounded-xl border bg-muted/20 p-4">
      <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
        {label}
      </p>
      {values.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {values.map((value) => (
            <Badge key={value} variant="outline" className="max-w-full text-[10px]">
              <span className="truncate">{value}</span>
            </Badge>
          ))}
        </div>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">No references published.</p>
      )}
    </div>
  );
}

function extractExplanation(value: ExplanationArtifact): string[] {
  const candidates = [value.summary, value.text, value.narrative, value.sentences];
  for (const candidate of candidates) {
    if (typeof candidate === "string" && candidate.trim()) return [candidate];
    if (
      Array.isArray(candidate) &&
      candidate.every((item) => typeof item === "string")
    ) {
      return candidate;
    }
  }
  const rendered = (value.sections ?? []).flatMap((section) =>
    section.sentences.map((sentence) => sentence.rendered_text),
  );
  return rendered.filter((line) => line.trim().length > 0);
}

function displayPlanValue(value: string | null | undefined): string {
  if (value === null || value === undefined || value.trim() === "") {
    return "Unavailable";
  }
  return value;
}

function formatPlanRange(
  lower: string | null | undefined,
  upper: string | null | undefined,
): string {
  return `${displayPlanValue(lower)} - ${displayPlanValue(upper)}`;
}
