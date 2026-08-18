"use client";

import { useEffect, useState } from "react";
import { ArrowDownRight, ArrowUpRight, Clock3, TriangleAlert } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { formatPrice, signalAgeMinutes, titleCase } from "@/lib/format";
import type { OpportunityDashboardItem, OpportunityPlan } from "@/lib/types";

function deriveStatus(
  stance: "BUY" | "SELL",
  plan: OpportunityPlan | null | undefined,
  currentPrice: number | null,
): { label: string; tone: "green" | "amber" | "red" | "neutral" } {
  if (!plan || currentPrice === null) {
    return { label: titleCase("UNAVAILABLE"), tone: "neutral" };
  }
  const entryLow = Number(plan.entry_zone.lower);
  const entryHigh = Number(plan.entry_zone.upper);
  const stop = Number(plan.invalidation_price);
  if (!Number.isFinite(entryLow) || !Number.isFinite(entryHigh)) {
    return { label: "UNAVAILABLE", tone: "neutral" };
  }
  if (stance === "SELL") {
    if (Number.isFinite(stop) && currentPrice >= stop) {
      return { label: "INVALIDATED", tone: "red" };
    }
    if (currentPrice >= entryLow && currentPrice <= entryHigh) {
      return { label: "ENTRY AVAILABLE", tone: "green" };
    }
    if (currentPrice < entryLow) {
      return { label: "ENTRY MISSED / WAIT", tone: "amber" };
    }
    return { label: "WAITING FOR ENTRY", tone: "neutral" };
  }
  if (stance === "BUY") {
    if (Number.isFinite(stop) && currentPrice <= stop) {
      return { label: "INVALIDATED", tone: "red" };
    }
    if (currentPrice >= entryLow && currentPrice <= entryHigh) {
      return { label: "ENTRY AVAILABLE", tone: "green" };
    }
    if (currentPrice > entryHigh) {
      return { label: "ENTRY MISSED / WAIT", tone: "amber" };
    }
    return { label: "WAITING FOR ENTRY", tone: "neutral" };
  }
  return { label: titleCase("UNAVAILABLE"), tone: "neutral" };
}

const STATUS_STYLES = {
  green: "border-emerald-400/40 bg-emerald-400/10 text-emerald-400",
  amber: "border-amber-400/40 bg-amber-400/10 text-amber-300",
  red: "border-rose-400/40 bg-rose-400/10 text-rose-400",
  neutral: "border-border text-muted-foreground",
} as const;

export function OpportunityCard({
  item,
  plan,
  currentPrice,
  confidence,
}: {
  item: OpportunityDashboardItem;
  plan?: OpportunityPlan | null;
  currentPrice?: string | null;
  confidence?: string | null;
}) {
  const bullish = item.stance === "BUY";
  const DirectionIcon = bullish ? ArrowUpRight : ArrowDownRight;
  const parsedCurrent = currentPrice ? Number(currentPrice) : null;
  const numericCurrent = parsedCurrent !== null && Number.isFinite(parsedCurrent) ? parsedCurrent : null;

  const [age, setAge] = useState(() => signalAgeMinutes(item.available_at));
  useEffect(() => {
    const id = setInterval(() => setAge(signalAgeMinutes(item.available_at)), 30_000);
    return () => clearInterval(id);
  }, [item.available_at]);

  const status = deriveStatus(item.stance as "BUY" | "SELL", plan ?? null, numericCurrent);
  const entryLow = plan?.entry_zone.lower ?? null;
  const entryHigh = plan?.entry_zone.upper ?? null;
  const stop = plan?.invalidation_price ?? null;
  const target1 = plan?.targets?.[0]?.price ?? null;
  const rr = plan?.targets?.[0]?.risk_reward ?? null;
  const isEntryMissed = status.tone === "amber" && status.label.includes("MISSED");
  const isInvalidated = status.label === "INVALIDATED";

  return (
    <Link
      href={`/opportunities/${encodeURIComponent(item.opportunity_id)}?as_of=${encodeURIComponent(item.available_at)}`}
      className="group block focus-visible:outline-none"
    >
      <Card className="overflow-hidden border-border/80 bg-card/95 transition group-hover:-translate-y-0.5 group-hover:border-primary/40 group-hover:shadow-lg group-hover:shadow-primary/5 group-focus-visible:ring-2 group-focus-visible:ring-primary">
        <CardContent className="p-0">
          <div className="flex items-center justify-between gap-3 border-b border-border/70 px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-semibold tracking-tight">
                {item.scope.instrument}
              </span>
              <Badge variant="outline" className="font-mono text-[9px]">
                {item.scope.timeframe}
              </Badge>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-muted-foreground">
                Rank {item.rank}
              </span>
              <span
                className={`flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-semibold ${
                  bullish
                    ? "bg-emerald-400/10 text-emerald-400"
                    : "bg-rose-400/10 text-rose-400"
                }`}
              >
                <DirectionIcon className="size-3" aria-hidden="true" />
                {item.stance}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-px bg-border/50">
            <Cell label="ENTRY" value={entryLow && entryHigh ? `${formatPrice(entryLow)} – ${formatPrice(entryHigh)}` : "Unavailable"} />
            <Cell label="CURRENT" value={numericCurrent !== null ? formatPrice(numericCurrent) : "Unavailable"} />
            <Cell
              label="STATUS"
              value={status.label}
              className={STATUS_STYLES[status.tone]}
            />
            <Cell label="STOP / INVALIDATION" value={stop ? formatPrice(stop) : "Unavailable"} />
            <Cell label="TARGET 1" value={target1 ? formatPrice(target1) : "Unavailable"} />
            <Cell label="RISK / REWARD" value={rr ?? "Unavailable"} />
          </div>

          <div className="flex items-center justify-between border-t border-border/70 px-4 py-2.5">
            <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
              <span className="flex items-center gap-1">
                <Clock3 className="size-3" aria-hidden="true" />
                {age}
              </span>
              <span>
                Confidence: {confidence ?? "Unavailable"}
              </span>
              <span>Quality: Unavailable</span>
            </div>
          </div>

          {(isEntryMissed || isInvalidated) && (
            <div className="flex items-center gap-1.5 border-t border-amber-400/20 bg-amber-400/5 px-4 py-2 text-[11px] text-amber-300/90">
              <TriangleAlert className="size-3 shrink-0" aria-hidden="true" />
              {isInvalidated
                ? "Signal invalidated at current price."
                : "Do not enter at current price."}
            </div>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}

function Cell({
  label,
  value,
  className,
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div className={`bg-card/95 px-3 py-2.5 ${className ?? ""}`}>
      <p className="text-[9px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-0.5 truncate font-mono text-xs font-medium tabular">
        {value}
      </p>
    </div>
  );
}
