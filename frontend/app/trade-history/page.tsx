import { History, ReceiptText } from "lucide-react";

import { ApiUnavailable, EmptyState } from "@/components/dashboard/data-states";
import { MetricCard } from "@/components/dashboard/metric-card";
import { PageHeader } from "@/components/dashboard/page-header";
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
import {
  formatCurrency,
  formatPercent,
  formatTimestamp,
  titleCase,
} from "@/lib/format";

export const metadata = { title: "Trade History" };

export default async function TradeHistoryPage() {
  const result = await getDashboardBundle();
  return (
    <>
      <PageHeader
        eyebrow="Execution ledger"
        title="Trade History"
        description="Completed simulated trades retained in immutable paper-trading evidence."
      />
      {!result.ok ? (
        <ApiUnavailable message={result.error} />
      ) : (
        <div className="space-y-6">
          <section className="grid gap-4 sm:grid-cols-2">
            <MetricCard
              label="Closed trades"
              value={String(result.data.dashboard.trades.length)}
              detail="Latest paper report"
              icon={History}
            />
            <MetricCard
              label="Orders"
              value={String(result.data.dashboard.orders.length)}
              detail="Simulated fills"
              icon={ReceiptText}
            />
          </section>
          <Card className="bg-card/95">
            <CardHeader>
              <CardTitle>Completed trades</CardTitle>
              <CardDescription>
                Entry, exit, cost, and realized paper P&amp;L
              </CardDescription>
            </CardHeader>
            <CardContent>
              {result.data.dashboard.trades.length ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Entry</TableHead>
                      <TableHead>Exit</TableHead>
                      <TableHead className="text-right">Quantity</TableHead>
                      <TableHead className="text-right">Net P&amp;L</TableHead>
                      <TableHead className="text-right">Return</TableHead>
                      <TableHead>Reason</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {result.data.dashboard.trades.map((trade) => (
                      <TableRow
                        key={`${trade.entry_timestamp}-${trade.exit_timestamp}`}
                      >
                        <TableCell>
                          {formatTimestamp(trade.entry_timestamp)}
                        </TableCell>
                        <TableCell>
                          {formatTimestamp(trade.exit_timestamp)}
                        </TableCell>
                        <TableCell className="tabular text-right">
                          {trade.quantity}
                        </TableCell>
                        <TableCell className="tabular text-right">
                          {formatCurrency(trade.net_profit_loss)}
                        </TableCell>
                        <TableCell className="tabular text-right">
                          {formatPercent(trade.return_fraction)}
                        </TableCell>
                        <TableCell>{titleCase(trade.exit_reason)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <EmptyState
                  title="No closed trades"
                  description="The paper portfolio has no completed trades in its latest immutable report."
                />
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
