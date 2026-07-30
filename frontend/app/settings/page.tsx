import { LockKeyhole, Settings2 } from "lucide-react";

import { ApiUnavailable, EmptyState } from "@/components/dashboard/data-states";
import { PageHeader } from "@/components/dashboard/page-header";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { getDashboardBundle } from "@/lib/api";
import { titleCase } from "@/lib/format";

export const metadata = { title: "Settings" };

export default async function SettingsPage() {
  const result = await getDashboardBundle();
  return (
    <>
      <PageHeader
        eyebrow="Runtime configuration"
        title="Settings"
        description="Read-only inspection of the active paper session. Configuration mutation is intentionally unavailable."
        actions={
          <Badge variant="outline" className="gap-2">
            <LockKeyhole className="size-3" />
            Read only
          </Badge>
        }
      />
      {!result.ok ? (
        <ApiUnavailable message={result.error} />
      ) : result.data.dashboard.settings ? (
        <div className="grid gap-4 xl:grid-cols-2">
          <SettingsCard
            title="Session"
            description="Market and scheduler context"
            values={{
              Session: result.data.dashboard.settings.session_name,
              Asset: `${result.data.dashboard.settings.asset_identifier}/${result.data.dashboard.settings.quote_currency}`,
              Timeframe: result.data.dashboard.settings.timeframe,
              "Execution interval": `${result.data.dashboard.settings.execution_interval_seconds} seconds`,
              "History observations": String(result.data.dashboard.settings.market_history_observations),
            }}
          />
          <SettingsCard title="Strategy" description="Deterministic signal policy" values={result.data.dashboard.settings.strategy} />
          <SettingsCard title="Risk framework" description="Active portfolio controls" values={result.data.dashboard.settings.risk} />
          <SettingsCard title="Portfolio simulation" description="Paper execution configuration" values={result.data.dashboard.settings.portfolio} />
        </div>
      ) : (
        <EmptyState title="No runtime settings" description="No paper-trading report is available to inspect." />
      )}
    </>
  );
}

function SettingsCard({
  title,
  description,
  values,
}: {
  title: string;
  description: string;
  values: Record<string, unknown>;
}) {
  return (
    <Card className="bg-card/95">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Settings2 className="size-4 text-primary" />
          {title}
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {Object.entries(values).map(([name, value], index) => (
          <div key={name}>
            {index ? <Separator className="mb-3" /> : null}
            <div className="flex items-start justify-between gap-5">
              <span className="text-xs text-muted-foreground">
                {titleCase(name)}
              </span>
              <span className="max-w-[62%] break-all text-right font-mono text-xs">
                {renderValue(value)}
              </span>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function renderValue(value: unknown): string {
  if (value === null || value === undefined) return "Unavailable";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
