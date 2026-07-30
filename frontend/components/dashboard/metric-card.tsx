import type { LucideIcon } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function MetricCard({
  label,
  value,
  detail,
  icon: Icon,
  tone = "default",
}: {
  label: string;
  value: string;
  detail?: string;
  icon: LucideIcon;
  tone?: "default" | "positive" | "negative";
}) {
  return (
    <Card className="min-h-32 bg-card/95">
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle className="text-xs font-medium uppercase tracking-[0.13em] text-muted-foreground">
          {label}
        </CardTitle>
        <Icon
          className={cn(
            "size-4 text-muted-foreground",
            tone === "positive" && "text-emerald-400",
            tone === "negative" && "text-rose-400",
          )}
          aria-hidden="true"
        />
      </CardHeader>
      <CardContent>
        <p className="tabular text-2xl font-semibold tracking-tight">{value}</p>
        {detail ? (
          <p className="mt-2 text-xs text-muted-foreground">{detail}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}
