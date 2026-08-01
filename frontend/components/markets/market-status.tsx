import { Activity, Clock3, Database, Radio } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { formatNumber, formatTimestamp, shortHash } from "@/lib/format";
import type { LiveMarketSnapshot } from "@/lib/types";

export function MarketStatus({ snapshot }: { snapshot: LiveMarketSnapshot }) {
  const candle = snapshot.candles.at(-1);
  return (
    <Card className="border-emerald-400/15 bg-card/95">
      <CardContent className="grid gap-5 p-5 sm:grid-cols-2 xl:grid-cols-4">
        <Status
          icon={Radio}
          label="Feed"
          value="Snapshot available"
          detail={`${snapshot.scope.instrument} · ${snapshot.scope.timeframe}`}
          positive
        />
        <Status
          icon={Activity}
          label="Last close"
          value={candle ? `$${formatNumber(candle.close, 2)}` : "Unavailable"}
          detail={candle ? `Volume ${formatNumber(candle.volume, 4)}` : "No candle"}
        />
        <Status
          icon={Clock3}
          label="Available at"
          value={formatTimestamp(snapshot.audit.available_at)}
          detail="UTC normalized"
        />
        <Status
          icon={Database}
          label="Immutable record"
          value={shortHash(snapshot.snapshot_id)}
          detail={shortHash(snapshot.audit.result_hash)}
        />
      </CardContent>
    </Card>
  );
}

function Status({
  icon: Icon,
  label,
  value,
  detail,
  positive = false,
}: {
  icon: typeof Activity;
  label: string;
  value: string;
  detail: string;
  positive?: boolean;
}) {
  return (
    <div className="flex gap-3">
      <span className="grid size-9 shrink-0 place-items-center rounded-lg border bg-muted/30">
        <Icon className="size-4 text-primary" />
      </span>
      <div className="min-w-0">
        <div className="mb-1 flex items-center gap-2">
          <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
            {label}
          </p>
          {positive ? <Badge className="size-1.5 rounded-full bg-emerald-400 p-0" /> : null}
        </div>
        <p className="truncate text-sm font-medium tabular">{value}</p>
        <p className="mt-1 truncate text-xs text-muted-foreground">{detail}</p>
      </div>
    </div>
  );
}
