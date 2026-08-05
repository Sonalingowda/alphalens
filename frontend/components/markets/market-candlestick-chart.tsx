"use client";

import {
  CandlestickSeries,
  ColorType,
  createChart,
  type IChartApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { useEffect, useRef, useState } from "react";
import { Skeleton } from "@/components/ui/skeleton";

import type { MarketCandle } from "@/lib/types";

export function MarketCandlestickChart({ candles }: { candles: MarketCandle[] }) {
  const container = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!container.current || candles.length === 0) return;
    let chart: IChartApi | null = createChart(container.current, {
      height: 360,
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#8b98aa",
        fontFamily: "Geist, sans-serif",
      },
      grid: {
        vertLines: { color: "rgba(140, 154, 176, 0.08)" },
        horzLines: { color: "rgba(140, 154, 176, 0.08)" },
      },
      rightPriceScale: { borderColor: "rgba(140, 154, 176, 0.14)" },
      timeScale: {
        borderColor: "rgba(140, 154, 176, 0.14)",
        timeVisible: true,
        secondsVisible: false,
      },
    });
    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#34d399",
      downColor: "#fb7185",
      wickUpColor: "#34d399",
      wickDownColor: "#fb7185",
      borderVisible: false,
    });
    const points = candles
      .map((candle) => ({
        time: Math.floor(new Date(candle.timestamp).getTime() / 1000) as UTCTimestamp,
        open: Number(candle.open),
        high: Number(candle.high),
        low: Number(candle.low),
        close: Number(candle.close),
      }))
      .filter((point) =>
        [point.open, point.high, point.low, point.close].every(Number.isFinite),
      )
      .sort((left, right) => Number(left.time) - Number(right.time))
      .filter((point, index, values) => index === 0 || point.time !== values[index - 1]?.time);
    series.setData(points);
    chart.timeScale().fitContent();
    setReady(true);
    return () => {
      chart?.remove();
      chart = null;
      setReady(false);
    };
  }, [candles]);

  return (
    <div>
      <div className="relative">
        <div ref={container} className="w-full" aria-label="BTCUSDT candlestick chart" />
        {(!ready || candles.length === 0) && <div className="absolute inset-0"><Skeleton className="h-80 w-full" /></div>}
      </div>
      <p className="mt-2 text-right text-[10px] text-muted-foreground">
        Charts by{" "}
        <a href="https://www.tradingview.com" className="hover:text-primary">
          TradingView
        </a>
      </p>
    </div>
  );
}
