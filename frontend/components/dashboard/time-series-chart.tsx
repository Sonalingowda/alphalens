"use client";

import {
  AreaSeries,
  ColorType,
  createChart,
  HistogramSeries,
  LineSeries,
  type IChartApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { useEffect, useRef } from "react";

import type { ChartPoint } from "@/lib/types";

export function TimeSeriesChart({
  data,
  kind = "area",
  color = "#44c6b4",
  percent = false,
  height = 260,
}: {
  data: ChartPoint[];
  kind?: "area" | "line" | "histogram";
  color?: string;
  percent?: boolean;
  height?: number;
}) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current || data.length === 0) return;
    let chart: IChartApi | null = createChart(container.current, {
      height,
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
      localization: {
        priceFormatter: percent
          ? (value: number) => `${(value * 100).toFixed(2)}%`
          : undefined,
      },
      handleScroll: false,
      handleScale: false,
    });
    const points = data
      .map((point) => ({
        time: Math.floor(new Date(point.timestamp).getTime() / 1000) as UTCTimestamp,
        value: Number(point.value),
      }))
      .filter((point) => Number.isFinite(point.value))
      .sort((left, right) => Number(left.time) - Number(right.time));
    const unique = points.filter(
      (point, index) =>
        index === 0 || point.time !== points[index - 1]?.time,
    );
    if (kind === "histogram") {
      const series = chart.addSeries(HistogramSeries, {
        color,
        priceFormat: { type: percent ? "percent" : "price" },
      });
      series.setData(unique);
    } else if (kind === "line") {
      const series = chart.addSeries(LineSeries, {
        color,
        lineWidth: 2,
        priceFormat: { type: percent ? "percent" : "price" },
      });
      series.setData(unique);
    } else {
      const series = chart.addSeries(AreaSeries, {
        lineColor: color,
        topColor: `${color}33`,
        bottomColor: `${color}05`,
        lineWidth: 2,
        priceFormat: { type: percent ? "percent" : "price" },
      });
      series.setData(unique);
    }
    chart.timeScale().fitContent();
    return () => {
      chart?.remove();
      chart = null;
    };
  }, [color, data, height, kind, percent]);

  return <div ref={container} className="w-full" aria-label="Time series chart" />;
}
