import { ArrowDownRight, ArrowUpRight, Clock3 } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { formatTimestamp, titleCase } from "@/lib/format";
import type { OpportunityDashboardItem, OpportunityPlan } from "@/lib/types";

export function OpportunityCard({
  item,
  plan,
}: {
  item: OpportunityDashboardItem;
  plan?: OpportunityPlan | null;
}) {
  const bullish = item.stance === "BUY";
  const DirectionIcon = bullish ? ArrowUpRight : ArrowDownRight;
  const planTargets = plan?.targets ?? [];

  return (
    <Link
      href={`/opportunities/${encodeURIComponent(item.opportunity_id)}?as_of=${encodeURIComponent(item.available_at)}`}
      className="group block focus-visible:outline-none"
    >
      <Card className="overflow-hidden border-border/80 bg-card/95 transition group-hover:-translate-y-0.5 group-hover:border-primary/40 group-hover:shadow-lg group-hover:shadow-primary/5 group-focus-visible:ring-2 group-focus-visible:ring-primary">
        <CardContent className="p-0">
          <div className="flex items-start justify-between gap-4 border-b border-border/70 p-5">
            <div>
              <div className="mb-2 flex items-center gap-2">
                <span className="font-mono text-base font-semibold tracking-tight">
                  {item.scope.instrument}
                </span>
                <Badge variant="outline" className="font-mono text-[10px]">
                  {item.scope.timeframe}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground">
                Rank {item.rank} · {titleCase(item.lifecycle_state)}
              </p>
            </div>
            <span
              className={`flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-semibold ${
                bullish
                  ? "bg-emerald-400/10 text-emerald-400"
                  : "bg-rose-400/10 text-rose-400"
              }`}
            >
              <DirectionIcon className="size-3.5" aria-hidden="true" />
              {item.stance}
            </span>
          </div>
          <div className="space-y-4 p-5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge
                variant={item.has_plan ? "secondary" : "outline"}
                className="font-mono text-[10px]"
              >
                {item.has_plan ? "Plan available" : "Plan unavailable"}
              </Badge>
              {item.detail_reference ? (
                <Badge variant="outline" className="font-mono text-[10px]">
                  {item.detail_reference}
                </Badge>
              ) : null}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {item.reason_codes.length ? (
                item.reason_codes.slice(0, 3).map((code) => (
                  <Badge key={code} variant="secondary" className="font-mono text-[10px]">
                    {code}
                  </Badge>
                ))
              ) : (
                <span className="text-xs text-muted-foreground">
                  No evidence summary published
                </span>
              )}
            </div>
            <div className="rounded-xl border border-border/70 bg-muted/20 p-4">
              <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
                Trade plan
              </p>
              {item.has_plan && plan ? (
                <div className="mt-3 space-y-3">
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="secondary" className="font-mono text-[10px]">
                      {plan.direction}
                    </Badge>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2">
                    <PlanFact
                      label="Entry"
                      value={formatPlanRange(plan.entry_zone.lower, plan.entry_zone.upper)}
                    />
                    <PlanFact
                      label="Stop / Invalidation"
                      value={displayPlanValue(plan.invalidation_price)}
                    />
                    <PlanFact
                      label="Target 1"
                      value={displayPlanValue(plan.targets[0]?.price)}
                    />
                    <PlanFact
                      label="Target 2"
                      value={displayPlanValue(plan.targets[1]?.price)}
                    />
                    <PlanFact
                      label="Risk / Reward"
                      value={displayPlanValue(plan.targets[0]?.risk_reward)}
                    />
                  </div>
                  {planTargets.length ? (
                    <div className="space-y-2">
                      <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                        Targets
                      </p>
                      <div className="space-y-2">
                        {planTargets.map((target, index) => (
                          <div
                            key={target.target_id}
                            className="rounded-lg border border-border/70 bg-background/70 p-3"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
                                Target {index + 1}
                              </p>
                              <p className="font-mono text-xs text-muted-foreground">
                                {target.target_id}
                              </p>
                            </div>
                            <div className="mt-2 grid gap-2 sm:grid-cols-2">
                              <PlanFact
                                label="Price"
                                value={displayPlanValue(target.price)}
                              />
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
                    </div>
                  ) : null}
                </div>
              ) : (
                <p className="mt-2 text-sm text-muted-foreground">Plan unavailable</p>
              )}
            </div>
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <Clock3 className="size-3.5" aria-hidden="true" />
                {formatTimestamp(item.available_at)}
              </span>
              <span>{titleCase(item.freshness_state)}</span>
            </div>
            {item.limitations.length ? (
              <p className="border-l-2 border-amber-400/50 pl-3 text-xs leading-5 text-amber-200/80">
                {item.limitations[0]}
              </p>
            ) : null}
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

function PlanFact({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-lg border border-border/70 bg-background/60 p-3">
      <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 text-sm font-medium">{value}</p>
    </div>
  );
}

function displayPlanValue(value: string | null | undefined): string {
  if (value === null || value === undefined || value.trim() === "") {
    return "Unavailable";
  }
  return value;
}

function formatPlanRange(lower: string | null | undefined, upper: string | null | undefined): string {
  return `${displayPlanValue(lower)} - ${displayPlanValue(upper)}`;
}
