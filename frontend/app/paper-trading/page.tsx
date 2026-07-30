import { CircleDollarSign, Radio, ReceiptText, ShieldCheck } from "lucide-react";

import { ChartCard } from "@/components/dashboard/chart-card";
import { ApiUnavailable, EmptyState } from "@/components/dashboard/data-states";
import { MetricCard } from "@/components/dashboard/metric-card";
import { PageHeader } from "@/components/dashboard/page-header";
import { SignalBadge } from "@/components/dashboard/signal-badge";
import { TimeSeriesChart } from "@/components/dashboard/time-series-chart";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getDashboardBundle } from "@/lib/api";
import { formatCurrency, formatTimestamp } from "@/lib/format";

export const metadata = { title: "Paper Trading" };

export default async function PaperTradingPage() {
  const result = await getDashboardBundle();
  return (
    <>
      <PageHeader
        eyebrow="Simulated execution"
        title="Paper Trading"
        description="Read-only execution flow from immutable paper reports. No broker connectivity or live orders."
      />
      {!result.ok ? (
        <ApiUnavailable message={result.error} />
      ) : (
        <div className="space-y-6">
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              label="Latest signal"
              value={result.data.dashboard.signal?.action ?? "Unavailable"}
              detail="Deterministic strategy output"
              icon={Radio}
            />
            <MetricCard
              label="Simulated orders"
              value={String(result.data.dashboard.orders.length)}
              detail="Latest paper report"
              icon={ReceiptText}
            />
            <MetricCard
              label="Closed trades"
              value={String(result.data.dashboard.trades.length)}
              detail="Paper execution only"
              icon={CircleDollarSign}
            />
            <MetricCard
              label="Risk events"
              value={String(result.data.dashboard.risk_events.length)}
              detail="Risk framework audit trail"
              icon={ShieldCheck}
            />
          </section>
          <ChartCard
            title="Position history"
            description="Market value of the simulated open position."
          >
            {result.data.dashboard.charts.position_history.length ? (
              <TimeSeriesChart data={result.data.dashboard.charts.position_history} />
            ) : (
              <EmptyState title="No position history" description="No paper portfolio history is available." />
            )}
          </ChartCard>
          <Card className="bg-card/95">
            <CardHeader>
              <CardTitle>Signal and order flow</CardTitle>
              <CardDescription>
                Ordered evidence from prediction through simulated execution
              </CardDescription>
            </CardHeader>
            <CardContent>
              {result.data.dashboard.signals.length ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Timestamp</TableHead>
                      <TableHead>Signal</TableHead>
                      <TableHead>Execution</TableHead>
                      <TableHead className="text-right">Notional</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {result.data.dashboard.signals.map((signal, index) => {
                      const order = result.data.dashboard.orders[index];
                      return (
                        <TableRow key={signal.source_prediction_hash}>
                          <TableCell>{formatTimestamp(signal.prediction_timestamp)}</TableCell>
                          <TableCell><SignalBadge action={signal.action} /></TableCell>
                          <TableCell>{order ? `${order.side} · ${formatTimestamp(order.execution_timestamp)}` : "No order"}</TableCell>
                          <TableCell className="tabular text-right">
                            {order ? formatCurrency(order.gross_notional) : "—"}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              ) : (
                <EmptyState title="No paper signals" description="No immutable paper signal evidence is available." />
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
