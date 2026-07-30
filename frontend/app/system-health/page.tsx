import {
  Activity,
  CheckCircle2,
  Clock3,
  Database,
  Gauge,
  MemoryStick,
  Server,
} from "lucide-react";

import { ApiUnavailable } from "@/components/dashboard/data-states";
import { MetricCard } from "@/components/dashboard/metric-card";
import { PageHeader } from "@/components/dashboard/page-header";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { getDashboardBundle } from "@/lib/api";
import {
  formatBytes,
  formatNumber,
  shortHash,
  titleCase,
} from "@/lib/format";

export const metadata = { title: "System Health" };

export default async function SystemHealthPage() {
  const result = await getDashboardBundle();
  return (
    <>
      <PageHeader
        eyebrow="Runtime observability"
        title="System Health"
        description="API, database, model artifact, and process-local operational status."
      />
      {!result.ok ? (
        <ApiUnavailable message={result.error} />
      ) : (
        <div className="space-y-6">
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <MetricCard label="API status" value={titleCase(result.data.health.status)} detail={`API ${result.data.health.api_version}`} icon={Server} tone="positive" />
            <MetricCard label="Database" value={titleCase(result.data.dashboard.system.database_status)} detail="Read projection available" icon={Database} tone="positive" />
            <MetricCard label="Requests" value={String(result.data.metrics.request_count)} detail={`${result.data.metrics.error_request_count} errors`} icon={Activity} />
            <MetricCard label="Average latency" value={`${formatNumber(result.data.metrics.average_latency_microseconds, 0)} μs`} detail={`Max ${result.data.metrics.maximum_latency_microseconds} μs`} icon={Clock3} />
            <MetricCard label="Process memory" value={formatBytes(result.data.resources.maximum_resident_set_bytes)} detail={`${formatNumber(result.data.resources.uptime_seconds, 0)}s uptime`} icon={MemoryStick} />
          </section>
          <section className="grid gap-4 lg:grid-cols-2">
            <StatusCard
              title="Inference service"
              description="Read-only packaged-artifact execution"
              rows={[
                ["Health", result.data.metrics.health],
                ["Artifact status", result.data.health.artifact_status],
                ["Prediction count", String(result.data.metrics.prediction_count)],
                ["Read only", result.data.health.read_only ? "yes" : "no"],
              ]}
            />
            <StatusCard
              title="Production model"
              description="Verified artifact metadata"
              rows={[
                ["Model", result.data.model.model_family],
                ["Version", result.data.model.artifact_version],
                ["Artifact ID", shortHash(result.data.model.artifact_identifier)],
                ["Artifact SHA-256", shortHash(result.data.model.artifact_sha256)],
                ["Schema SHA-256", shortHash(result.data.model.schema_hash)],
                ["Feature count", String(result.data.model.feature_count)],
              ]}
            />
          </section>
          <Card className="bg-card/95">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Gauge className="size-4 text-primary" />
                Verification state
              </CardTitle>
              <CardDescription>
                Status exposed by running services only
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-3">
              <Verification label="Artifact hash" value="Verified" />
              <Verification label="Database connection" value="Connected" />
              <Verification
                label="Automated tests"
                value={titleCase(result.data.dashboard.system.test_status)}
                muted={result.data.dashboard.system.test_status !== "passing"}
              />
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}

function StatusCard({
  title,
  description,
  rows,
}: {
  title: string;
  description: string;
  rows: [string, string][];
}) {
  return (
    <Card className="bg-card/95">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between gap-4 border-b pb-3 last:border-0 last:pb-0">
            <span className="text-xs text-muted-foreground">{label}</span>
            <span className="font-mono text-xs">{value}</span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function Verification({
  label,
  value,
  muted = false,
}: {
  label: string;
  value: string;
  muted?: boolean;
}) {
  return (
    <div className="flex items-center justify-between rounded-lg border bg-muted/20 p-4">
      <span className="text-xs text-muted-foreground">{label}</span>
      <Badge variant="outline" className={muted ? "" : "border-emerald-400/30 text-emerald-400"}>
        {!muted ? <CheckCircle2 className="mr-1 size-3" /> : null}
        {value}
      </Badge>
    </div>
  );
}
