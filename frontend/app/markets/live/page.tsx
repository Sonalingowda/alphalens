import Link from "next/link";

import { ApiUnavailable, EmptyState } from "@/components/dashboard/data-states";
import { PageHeader } from "@/components/dashboard/page-header";
import { MarketCandlestickChart } from "@/components/markets/market-candlestick-chart";
import { MarketStatus } from "@/components/markets/market-status";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getLiveMarket } from "@/lib/api";

type MarketSearchParams = Promise<{ timeframe?: string }>;

export const metadata = { title: "Live Market Status" };

export default async function LiveMarketPage({
  searchParams,
}: {
  searchParams: MarketSearchParams;
}) {
  const requested = await searchParams;
  const timeframe = ["5m", "10m", "15m"].includes(requested.timeframe ?? "")
    ? requested.timeframe!
    : "5m";
  const market = await getLiveMarket("BTCUSDT", timeframe);

  return (
    <>
      <PageHeader
        eyebrow="Live market data"
        title="BTCUSDT market status"
        description="UTC-normalized completed candles from the immutable Binance Spot snapshot stream. No indicators or signals are computed on this page."
        actions={
          <div className="flex gap-2">
            {["5m", "10m", "15m"].map((value) => (
              <Button key={value} variant={value === timeframe ? "default" : "outline"} size="sm" render={<Link href={`/markets/live?timeframe=${value}`} />}>
                {value}
              </Button>
            ))}
          </div>
        }
      />
      {!market.ok ? (
        <ApiUnavailable message={market.error} />
      ) : (
        <div className="space-y-6">
          <MarketStatus snapshot={market.data} />
          <Card className="bg-card/95">
            <CardHeader>
              <CardTitle>Completed candles</CardTitle>
              <CardDescription>
                Canonical OHLC data only; the visible range reflects snapshots returned by the API.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {market.data.candles.length ? (
                <MarketCandlestickChart candles={market.data.candles} />
              ) : (
                <EmptyState title="No completed candles" description="The live market repository has no completed candle for this scope." />
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
