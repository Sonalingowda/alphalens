import { ArrowDownRight, ArrowUpRight, Banknote, BriefcaseBusiness, Wallet } from "lucide-react";

import { ChartCard } from "@/components/dashboard/chart-card";
import { ApiUnavailable, EmptyState } from "@/components/dashboard/data-states";
import { MetricCard } from "@/components/dashboard/metric-card";
import { PageHeader } from "@/components/dashboard/page-header";
import { TimeSeriesChart } from "@/components/dashboard/time-series-chart";
import { getDashboardBundle } from "@/lib/api";
import { formatCurrency } from "@/lib/format";

export const metadata = { title: "Portfolio" };

export default async function PortfolioPage() {
  const result = await getDashboardBundle();
  return (
    <>
      <PageHeader
        eyebrow="Paper portfolio"
        title="Portfolio"
        description="Cash, equity, positions, returns, and drawdown from the immutable simulated portfolio ledger."
      />
      {!result.ok ? (
        <ApiUnavailable message={result.error} />
      ) : (
        <div className="space-y-6">
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Portfolio value" value={formatCurrency(result.data.dashboard.portfolio.portfolio_value)} detail="Current paper equity" icon={Wallet} />
            <MetricCard label="Cash" value={formatCurrency(result.data.dashboard.portfolio.cash)} detail="Unallocated balance" icon={Banknote} />
            <MetricCard label="Unrealized P&L" value={formatCurrency(result.data.dashboard.portfolio.unrealized_pnl)} detail={`${result.data.dashboard.portfolio.open_position_count} open position`} icon={BriefcaseBusiness} />
            <MetricCard
              label="Daily P&L"
              value={formatCurrency(result.data.dashboard.portfolio.daily_pnl)}
              detail={`Realized ${formatCurrency(result.data.dashboard.portfolio.realized_pnl)}`}
              icon={Number(result.data.dashboard.portfolio.daily_pnl ?? 0) >= 0 ? ArrowUpRight : ArrowDownRight}
              tone={Number(result.data.dashboard.portfolio.daily_pnl ?? 0) >= 0 ? "positive" : "negative"}
            />
          </section>
          <section className="grid gap-4 xl:grid-cols-2">
            <ChartCard title="Equity curve" description="Total simulated portfolio value.">
              {result.data.dashboard.charts.equity_curve.length ? <TimeSeriesChart data={result.data.dashboard.charts.equity_curve} /> : <EmptyState title="No equity curve" description="No portfolio observations are available." />}
            </ChartCard>
            <ChartCard title="Daily returns" description="Daily portfolio return observations.">
              {result.data.dashboard.charts.daily_returns.length ? <TimeSeriesChart data={result.data.dashboard.charts.daily_returns} kind="histogram" percent color="#6d91e8" /> : <EmptyState title="No daily returns" description="No return observations are available." />}
            </ChartCard>
            <ChartCard title="Drawdown" description="Decline from the running portfolio peak.">
              {result.data.dashboard.charts.drawdown.length ? <TimeSeriesChart data={result.data.dashboard.charts.drawdown} kind="area" percent color="#e56b6f" /> : <EmptyState title="No drawdown series" description="No portfolio observations are available." />}
            </ChartCard>
            <ChartCard title="Position exposure" description="Open position market value over time.">
              {result.data.dashboard.charts.position_history.length ? <TimeSeriesChart data={result.data.dashboard.charts.position_history} kind="line" color="#d5a64c" /> : <EmptyState title="No position history" description="No position observations are available." />}
            </ChartCard>
          </section>
        </div>
      )}
    </>
  );
}
