import Link from "next/link";

import { EmptyState } from "@/components/dashboard/data-states";
import { Badge } from "@/components/ui/badge";
import { formatTimestamp, titleCase } from "@/lib/format";
import type { OpportunityDashboardItem } from "@/lib/types";

export function HistoricalOpportunitiesTable({ items }: { items: OpportunityDashboardItem[] }) {
  if (items.length === 0) {
    return <EmptyState title="No opportunity history" description="Completed, invalidated, expired and missed-entry records will appear here when persisted." />;
  }
  return (
    <div className="rounded-xl border border-border/80 bg-card/90">
      <div className="hidden overflow-hidden md:block">
      <table className="w-full table-fixed text-left text-xs">
        <caption className="sr-only">Historical AlphaLens opportunities</caption>
        <colgroup><col className="w-[21%]" /><col className="w-[14%]" /><col className="w-[25%]" /><col className="w-[24%]" /><col className="w-[16%]" /></colgroup>
        <thead className="border-b border-border/70 text-[10px] uppercase tracking-[0.14em] text-muted-foreground"><tr><th className="px-4 py-3">Instrument</th><th className="px-4 py-3">Direction</th><th className="px-4 py-3">Lifecycle</th><th className="px-4 py-3">Evidence</th><th className="px-4 py-3">Record</th></tr></thead>
        <tbody className="divide-y divide-border/60">{items.map((item) => <tr key={item.opportunity_id} className="hover:bg-muted/20"><td className="break-words px-4 py-3 font-mono">{item.scope.instrument} · {item.scope.timeframe}</td><td className="px-4 py-3"><Badge variant="outline">{item.stance === "BUY" ? "Long" : "Short"}</Badge></td><td className="break-words px-4 py-3">{titleCase(item.lifecycle_state)}</td><td className="break-words px-4 py-3 font-mono text-muted-foreground">{formatTimestamp(item.available_at)}</td><td className="break-words px-4 py-3"><Link className="text-primary hover:underline" href={`/opportunities/${encodeURIComponent(item.opportunity_id)}?as_of=${encodeURIComponent(item.available_at)}`}>Open record</Link></td></tr>)}</tbody>
      </table>
      </div>
      <div className="divide-y divide-border/60 md:hidden">
        {items.map((item) => <article key={item.opportunity_id} className="space-y-3 p-4">
          <div className="flex items-start justify-between gap-3"><div><p className="font-mono text-sm">{item.scope.instrument} · {item.scope.timeframe}</p><p className="mt-1 text-xs text-muted-foreground">{formatTimestamp(item.available_at)}</p></div><Badge variant="outline">{item.stance === "BUY" ? "Long" : "Short"}</Badge></div>
          <div className="flex items-center justify-between gap-3 text-xs"><span className="text-muted-foreground">Lifecycle</span><span className="text-right">{titleCase(item.lifecycle_state)}</span></div>
          <Link className="inline-block text-xs text-primary hover:underline" href={`/opportunities/${encodeURIComponent(item.opportunity_id)}?as_of=${encodeURIComponent(item.available_at)}`}>Open record</Link>
        </article>)}
      </div>
    </div>
  );
}
