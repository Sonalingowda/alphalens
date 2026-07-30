import { Activity, Clock3, Hash, TrendingUp } from "lucide-react";

import { ChartCard } from "@/components/dashboard/chart-card";
import { ApiUnavailable, EmptyState } from "@/components/dashboard/data-states";
import { MetricCard } from "@/components/dashboard/metric-card";
import { PageHeader } from "@/components/dashboard/page-header";
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
import { formatPercent, formatTimestamp, shortHash } from "@/lib/format";

export const metadata = { title: "Predictions" };

export default async function PredictionsPage() {
  const result = await getDashboardBundle();
  return (
    <>
      <PageHeader
        eyebrow="Inference evidence"
        title="Predictions"
        description="Deterministic outputs produced by the packaged Ridge artifact. The dashboard never computes predictions locally."
      />
      {!result.ok ? (
        <ApiUnavailable message={result.error} />
      ) : (
        <div className="space-y-6">
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              label="Latest prediction"
              value={formatPercent(
                result.data.dashboard.prediction?.predicted_forward_return,
                3,
              )}
              detail="Forward log return"
              icon={TrendingUp}
            />
            <MetricCard
              label="Horizon"
              value={`${result.data.model.horizon_observations} days`}
              detail={result.data.model.target_name}
              icon={Clock3}
            />
            <MetricCard
              label="Evidence rows"
              value={String(result.data.dashboard.predictions.length)}
              detail="Latest paper report"
              icon={Activity}
            />
            <MetricCard
              label="Artifact"
              value={shortHash(result.data.model.artifact_identifier)}
              detail={`Schema ${shortHash(result.data.model.schema_hash)}`}
              icon={Hash}
            />
          </section>
          <ChartCard
            title="Prediction history"
            description="Forward log return predictions in timestamp order."
          >
            {result.data.dashboard.charts.prediction_history.length ? (
              <TimeSeriesChart
                data={result.data.dashboard.charts.prediction_history}
                kind="histogram"
                percent
              />
            ) : (
              <EmptyState
                title="No prediction history"
                description="No immutable prediction evidence is available."
              />
            )}
          </ChartCard>
          <Card className="bg-card/95">
            <CardHeader>
              <CardTitle>Prediction evidence</CardTitle>
              <CardDescription>
                Exact values and hashes returned by production inference
              </CardDescription>
            </CardHeader>
            <CardContent>
              {result.data.dashboard.predictions.length ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Timestamp</TableHead>
                      <TableHead className="text-right">Prediction</TableHead>
                      <TableHead>Feature vector</TableHead>
                      <TableHead>Evidence</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {result.data.dashboard.predictions.map((prediction) => (
                      <TableRow key={prediction.evidence_hash}>
                        <TableCell>
                          {formatTimestamp(prediction.prediction_timestamp)}
                        </TableCell>
                        <TableCell className="tabular text-right">
                          {formatPercent(
                            prediction.predicted_forward_return,
                            4,
                          )}
                        </TableCell>
                        <TableCell className="font-mono text-xs">
                          {shortHash(prediction.feature_vector_hash)}
                        </TableCell>
                        <TableCell className="font-mono text-xs">
                          {shortHash(prediction.evidence_hash)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <EmptyState
                  title="No prediction evidence"
                  description="Run an authorized paper cycle to create prediction evidence."
                />
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
