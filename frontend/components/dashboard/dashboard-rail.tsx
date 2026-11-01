import { Activity, CircleAlert, Database, RadioTower } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatPrice, formatTimestamp, titleCase } from "@/lib/format";
import type { LiveMarketSnapshot, LocalRuntimeStatus, OpportunityDashboardItem } from "@/lib/types";

export function DashboardRail({
  runtime,
  market,
  items,
}: {
  runtime: LocalRuntimeStatus | null;
  market: LiveMarketSnapshot | null;
  items: OpportunityDashboardItem[];
}) {
  const candle = market?.candles.at(-1);
  const worker = runtime?.worker;
  const feedState = worker?.connection.state ?? "unavailable";
  const healthy = worker?.connection.healthy === true && worker.worker_status === "RUNNING";
  const recent = [...new Map(items.map((item) => [item.opportunity_id, item])).values()]
    .sort((left, right) => right.available_at.localeCompare(left.available_at))
    .slice(0, 5);

  return (
    <aside className="space-y-4" aria-label="Dashboard status rail">
      <Card className="border-primary/20 bg-card/90">
        <CardHeader className="flex-row items-center justify-between space-y-0 pb-3">
          <CardTitle className="text-sm">System Status</CardTitle>
          <span className={`size-2 rounded-full ${healthy ? "bg-emerald-400" : "bg-amber-400"}`} />
        </CardHeader>
        <CardContent className="space-y-3 text-xs">
          <StatusRow icon={RadioTower} label="Worker" value={worker?.worker_status ?? "Unavailable"} />
          <StatusRow icon={Activity} label="Feed" value={titleCase(feedState)} />
          <StatusRow icon={Database} label="Persistence" value={worker?.checkpoint.last_error ? "Attention required" : worker ? "Available" : "Unavailable"} />
          <div className="rounded-md border border-amber-400/20 bg-amber-400/5 px-3 py-2 text-amber-200">
            <p className="font-medium">Model unavailable</p>
            <p className="mt-1 text-[11px] text-amber-200/70">No approved predictive artifact is installed.</p>
          </div>
        </CardContent>
      </Card>

      <Card className="bg-card/90">
        <CardHeader className="pb-3"><CardTitle className="text-sm">Snapshot</CardTitle></CardHeader>
        <CardContent className="space-y-3 text-xs">
          <div className="flex items-end justify-between gap-3">
            <span className="text-muted-foreground">BTCUSDT · 5m</span>
            <span className="font-mono text-lg font-semibold">{candle ? `$${formatPrice(candle.close)}` : "Unavailable"}</span>
          </div>
          <div className="grid grid-cols-2 gap-3 border-t border-border/70 pt-3">
            <Metric label="Last close" value={candle ? formatTimestamp(candle.timestamp) : "Unavailable"} />
            <Metric label="Available" value={market ? formatTimestamp(market.audit.available_at) : "Unavailable"} />
          </div>
          {!healthy ? <p className="flex gap-2 rounded-md border border-amber-400/20 bg-amber-400/5 px-3 py-2 text-amber-200"><CircleAlert className="size-3.5 shrink-0" />Feed is stopped or stale; no actionable opportunities are verified.</p> : null}
        </CardContent>
      </Card>

      <Card className="bg-card/90">
        <CardHeader className="flex-row items-center justify-between space-y-0 pb-3"><CardTitle className="text-sm">Recent Events</CardTitle><Badge variant="outline">Persisted</Badge></CardHeader>
        <CardContent>
          {recent.length === 0 ? <p className="text-xs text-muted-foreground">No persisted opportunity events are available.</p> : <div className="space-y-3">{recent.map((item) => <div key={item.opportunity_id} className="border-l border-primary/40 pl-3"><p className="text-xs font-medium">{titleCase(item.lifecycle_state)}</p><p className="mt-1 text-[11px] text-muted-foreground">{item.stance} · {formatTimestamp(item.available_at)}</p></div>)}</div>}
        </CardContent>
      </Card>
    </aside>
  );
}

function StatusRow({ icon: Icon, label, value }: { icon: typeof Activity; label: string; value: string }) {
  return <div className="flex items-center justify-between gap-3"><span className="flex items-center gap-2 text-muted-foreground"><Icon className="size-3.5 text-primary" />{label}</span><span className="font-mono text-right">{value}</span></div>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div><p className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">{label}</p><p className="mt-1 break-words font-mono text-[11px]">{value}</p></div>;
}
