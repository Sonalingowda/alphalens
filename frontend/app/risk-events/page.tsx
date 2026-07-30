import { ShieldAlert, ShieldCheck } from "lucide-react";

import { ApiUnavailable, EmptyState } from "@/components/dashboard/data-states";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getDashboardBundle } from "@/lib/api";
import { formatCurrency, formatTimestamp, titleCase } from "@/lib/format";

export const metadata = { title: "Risk Events" };

export default async function RiskEventsPage() {
  const result = await getDashboardBundle();
  return (
    <>
      <PageHeader
        eyebrow="Portfolio controls"
        title="Risk Events"
        description="Accepted decisions, rejections, forced exits, and portfolio protection events from the immutable risk report."
      />
      {!result.ok ? (
        <ApiUnavailable message={result.error} />
      ) : (
        <div className="space-y-6">
          <section className="grid gap-4 sm:grid-cols-2">
            <MetricCard
              label="Risk events"
              value={String(result.data.dashboard.risk_events.length)}
              detail="Latest verified report"
              icon={ShieldAlert}
            />
            <MetricCard
              label="Framework"
              value={
                result.data.dashboard.system.risk_framework_version ??
                "Unavailable"
              }
              detail="Immutable configuration"
              icon={ShieldCheck}
            />
          </section>
          <Card className="bg-card/95">
            <CardHeader>
              <CardTitle>Risk audit trail</CardTitle>
              <CardDescription>
                Each entry is linked to its source report
              </CardDescription>
            </CardHeader>
            <CardContent>
              {result.data.dashboard.risk_events.length ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Timestamp</TableHead>
                      <TableHead>Event</TableHead>
                      <TableHead>Action</TableHead>
                      <TableHead>Rules</TableHead>
                      <TableHead className="text-right">Allocation</TableHead>
                      <TableHead>Reason</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {result.data.dashboard.risk_events.map((event, index) => (
                      <TableRow
                        key={`${event.report_id}-${event.timestamp}-${index}`}
                      >
                        <TableCell>{formatTimestamp(event.timestamp)}</TableCell>
                        <TableCell>{titleCase(event.event_type)}</TableCell>
                        <TableCell>
                          <Badge variant="outline">
                            {titleCase(event.action)}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-xs">
                          {event.rule_names.length
                            ? event.rule_names.map(titleCase).join(", ")
                            : "None"}
                        </TableCell>
                        <TableCell className="tabular text-right">
                          {formatCurrency(event.approved_cash_allocation)}
                        </TableCell>
                        <TableCell className="max-w-64 text-xs text-muted-foreground">
                          {event.reason}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <EmptyState
                  title="No risk events"
                  description="No immutable risk-management report is available."
                />
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
