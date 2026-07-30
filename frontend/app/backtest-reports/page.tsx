import { BarChart3, CalendarRange, FlaskConical, ReceiptText } from "lucide-react";

import { ChartCard } from "@/components/dashboard/chart-card";
import { ApiUnavailable, EmptyState } from "@/components/dashboard/data-states";
import { MetricCard } from "@/components/dashboard/metric-card";
import { PageHeader } from "@/components/dashboard/page-header";
import { TimeSeriesChart } from "@/components/dashboard/time-series-chart";
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
  formatNumber,
  formatPercent,
  formatTimestamp,
  shortHash,
  titleCase,
} from "@/lib/format";
import type { BacktestReport } from "@/lib/types";

export const metadata = { title: "Backtest Reports" };

export default async function BacktestReportsPage() {
  const result = await getDashboardBundle();
  return (
    <>
      <PageHeader
        eyebrow="Immutable evidence"
        title="Backtest Reports"
        description="Previously persisted backtest evidence. The dashboard does not run or modify simulations."
      />
      {!result.ok ? (
        <ApiUnavailable message={result.error} />
      ) : result.data.dashboard.backtest_reports.length ? (
        <Reports reports={result.data.dashboard.backtest_reports} />
      ) : (
        <EmptyState
          title="No backtest reports"
          description="No verified immutable backtest evidence is available."
        />
      )}
    </>
  );
}

function Reports({ reports }: { reports: BacktestReport[] }) {
  const latest = reports[0];
  if (!latest) return null;
  const metric = (name: string) => latest.metrics[name];
  return (
    <div className="space-y-6">
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Reports" value={String(reports.length)} detail="Immutable records" icon={FlaskConical} />
        <MetricCard label="Total return" value={formatPercent(metric("total_return") as string)} detail="Latest report" icon={BarChart3} />
        <MetricCard label="Sharpe ratio" value={formatNumber(metric("sharpe_ratio") as string)} detail="Latest report" icon={CalendarRange} />
        <MetricCard label="Trades" value={String(latest.trade_log.length)} detail="Latest report" icon={ReceiptText} />
      </section>
      <ChartCard title="Backtest equity curve" description={`${formatTimestamp(latest.period_start)} to ${formatTimestamp(latest.period_end)}`}>
        <TimeSeriesChart
          data={latest.equity_curve.map((point) => ({
            timestamp: point.timestamp,
            value: point.portfolio_value,
          }))}
        />
      </ChartCard>
      <section className="grid gap-4 xl:grid-cols-2">
        {reports.map((report) => (
          <Card key={report.report_id} className="bg-card/95">
            <CardHeader>
              <div className="flex items-center justify-between gap-3">
                <CardTitle>Report {shortHash(report.report_id)}</CardTitle>
                <Badge variant="outline">v{report.report_version}</Badge>
              </div>
              <CardDescription>
                Generated {formatTimestamp(report.generated_at)}
              </CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-4">
              {Object.entries(report.metrics).map(([name, value]) => (
                <div key={name} className="rounded-lg border bg-muted/20 p-3">
                  <p className="text-xs text-muted-foreground">
                    {titleCase(name)}
                  </p>
                  <p className="tabular mt-1 font-medium">
                    {value === null ? "Unavailable" : String(value)}
                  </p>
                </div>
              ))}
              <div className="col-span-2 border-t pt-3 text-xs text-muted-foreground">
                Result hash{" "}
                <span className="font-mono text-foreground">
                  {shortHash(report.result_hash)}
                </span>
              </div>
            </CardContent>
          </Card>
        ))}
      </section>
    </div>
  );
}
