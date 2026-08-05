import { ArrowDownRight, ArrowUpRight, Clock3 } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { formatTimestamp, titleCase } from "@/lib/format";
import type { OpportunityDashboardItem } from "@/lib/types";

export function OpportunityCard({ item }: { item: OpportunityDashboardItem }) {
  const bullish = item.stance === "BUY";
  const DirectionIcon = bullish ? ArrowUpRight : ArrowDownRight;

  return (
    <Link
      href={`/opportunities/${encodeURIComponent(item.opportunity_id)}`}
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
