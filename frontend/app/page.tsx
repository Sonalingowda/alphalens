import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  BriefcaseBusiness,
  CircleDollarSign,
  ShieldAlert,
  Wallet,
} from "lucide-react";

import { ChartCard } from "@/components/dashboard/chart-card";
import { ApiUnavailable, EmptyState } from "@/components/dashboard/data-states";
import { MetricCard } from "@/components/dashboard/metric-card";
import { PageHeader } from "@/components/dashboard/page-header";
import { SignalBadge } from "@/components/dashboard/signal-badge";
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
  formatCurrency,
  formatPercent,
  formatTimestamp,
  shortHash,
} from "@/lib/format";
import type { DashboardBundle } from "@/lib/types";

export default async function DashboardPage() {
  const result = await getDashboardBundle();

  return (
    <>
      <PageHeader
        eyebrow="Live operations"
        title="Dashboard"
        description="A read-only view of verified prediction, paper portfolio, risk, and model evidence."
        actions={
          <Badge variant="outline" className="w-fit gap-2">
            <span
              className={`size-1.5 rounded-full ${
                result.ok ? "bg-emerald-400" : "bg-rose-400"
              }`}
            />
            {result.ok ? "API operational" : "API unavailable"}
          </Badge>
        }
      />
      {!result.ok ? (
        <ApiUnavailable message={result.error} />
      ) : (
        <DashboardContent data={result.data} />
      )}
    </>
  );
}

function DashboardContent({ data }: { data: DashboardBundle }) {
  const { dashboard, model } = data;
  const prediction = dashboard.prediction;
  const dailyPnl = Number(dashboard.portfolio.daily_pnl ?? 0);
  const predicted = Number(prediction?.predicted_forward_return ?? 0);
  return (
    <div className="space-y-6">
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Current prediction"
          value={
            prediction
              ? formatPercent(prediction.predicted_forward_return, 3)
              : "Unavailable"
          }
          detail={
            prediction
              ? `${prediction.horizon_observations}-observation forward log return`
              : "No immutable prediction evidence"
          }
          icon={predicted >= 0 ? ArrowUpRight : ArrowDownRight}
          tone={predicted >= 0 ? "positive" : "negative"}
        />
        <MetricCard
          label="Portfolio value"
          value={formatCurrency(dashboard.portfolio.portfolio_value)}
          detail={`Cash ${formatCurrency(dashboard.portfolio.cash)}`}
          icon={Wallet}
        />
        <MetricCard
          label="Daily P&L"
          value={formatCurrency(dashboard.portfolio.daily_pnl)}
          detail={`Realized ${formatCurrency(dashboard.portfolio.realized_pnl)}`}
          icon={dailyPnl >= 0 ? ArrowUpRight : ArrowDownRight}
          tone={dailyPnl >= 0 ? "positive" : "negative"}
        />
        <MetricCard
          label="Unrealized P&L"
          value={formatCurrency(dashboard.portfolio.unrealized_pnl)}
          detail={`${dashboard.portfolio.open_position_count} open position`}
          icon={BriefcaseBusiness}
        />
      </section>

      <section className="grid gap-4 lg:grid-cols-[1.35fr_.65fr]">
        <ChartCard
          title="Portfolio equity"
          description="Immutable paper portfolio history from the latest report."
        >
          {dashboard.charts.equity_curve.length ? (
            <TimeSeriesChart data={dashboard.charts.equity_curve} />
          ) : (
            <EmptyState
              title="No equity observations"
              description="The latest paper report has not recorded an equity curve."
            />
          )}
        </ChartCard>
        <Card className="bg-card/95">
          <CardHeader>
            <CardTitle>Latest decision</CardTitle>
            <CardDescription>
              Prediction and deterministic strategy output
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="flex items-center justify-between rounded-lg border bg-muted/30 p-4">
              <span className="text-sm text-muted-foreground">Signal</span>
              <SignalBadge action={dashboard.signal?.action ?? null} />
            </div>
            <Detail
              label="Prediction timestamp"
              value={formatTimestamp(prediction?.prediction_timestamp)}
            />
            <Detail
              label="Confidence"
              value={
                dashboard.confidence.available
                  ? "Available"
                  : "Not produced by model"
              }
            />
            <Detail
              label="Model artifact"
              value={shortHash(model.artifact_identifier)}
              mono
            />
            <Detail label="Model version" value={model.artifact_version} />
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <MetricCard
          label="Closed trades"
          value={String(dashboard.portfolio.closed_trade_count)}
          detail={`${dashboard.orders.length} simulated orders`}
          icon={CircleDollarSign}
        />
        <MetricCard
          label="Risk events"
          value={String(dashboard.risk_events.length)}
          detail="Latest immutable risk report"
          icon={ShieldAlert}
        />
        <MetricCard
          label="API requests"
          value={String(data.metrics.request_count)}
          detail={`${data.metrics.prediction_count} prediction requests`}
          icon={Activity}
        />
      </section>
    </div>
  );
}

function Detail({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b pb-3 last:border-0 last:pb-0">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span
        className={`max-w-[65%] text-right text-xs font-medium ${
          mono ? "font-mono" : ""
        }`}
      >
        {value}
      </span>
    </div>
  );
}
