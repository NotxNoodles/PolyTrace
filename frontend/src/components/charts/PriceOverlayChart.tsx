"use client";

import { useEffect, useRef } from "react";
import type { PolyPricePoint, SpotPricePoint } from "@/types";

interface Props {
  polySeries: PolyPricePoint[];
  spotSeries: SpotPricePoint[];
  spotSymbol: string;
  height?: number;
}

export default function PriceOverlayChart({
  polySeries,
  spotSeries,
  spotSymbol,
  height = 380,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    let disposed = false;

    (async () => {
      const { createChart } = await import("lightweight-charts");

      if (disposed || !containerRef.current) return;

      if (chartRef.current) {
        chartRef.current.remove();
      }

      const chart = createChart(containerRef.current, {
        width: containerRef.current.clientWidth,
        height,
        layout: {
          background: { color: "#0f0f18" },
          textColor: "#6b7280",
          fontSize: 11,
        },
        grid: {
          vertLines: { color: "#1a1a2e" },
          horzLines: { color: "#1a1a2e" },
        },
        crosshair: {
          mode: 0,
        },
        rightPriceScale: {
          borderColor: "#22223a",
          scaleMargins: { top: 0.1, bottom: 0.2 },
        },
        timeScale: {
          borderColor: "#22223a",
          timeVisible: true,
          secondsVisible: false,
        },
      });
      chartRef.current = chart;

      const polySer = chart.addLineSeries({
        color: "#00f5a0",
        lineWidth: 2,
        priceFormat: { type: "price", precision: 4, minMove: 0.0001 },
        title: "P(Yes)",
      });

      const polyData = polySeries
        .map((p) => ({
          time: Math.floor(new Date(p.t).getTime() / 1000) as any,
          value: p.yes,
        }))
        .sort((a: any, b: any) => a.time - b.time);

      if (polyData.length > 0) {
        polySer.setData(polyData);
      }

      if (spotSeries.length > 0) {
        const spotMin = Math.min(...spotSeries.map((s) => s.l));
        const spotMax = Math.max(...spotSeries.map((s) => s.h));
        const spotRange = spotMax - spotMin || 1;

        const spotNormalized = spotSeries
          .map((s) => ({
            time: Math.floor(new Date(s.t).getTime() / 1000) as any,
            value: (s.c - spotMin) / spotRange,
          }))
          .sort((a: any, b: any) => a.time - b.time);

        const spotSer = chart.addLineSeries({
          color: "#00d2ff",
          lineWidth: 2,
          lineStyle: 2,
          priceFormat: { type: "price", precision: 4, minMove: 0.0001 },
          title: `${spotSymbol} (norm)`,
        });
        spotSer.setData(spotNormalized);
      }

      const volData = polySeries
        .filter((p) => p.vol != null && p.vol > 0)
        .map((p) => ({
          time: Math.floor(new Date(p.t).getTime() / 1000) as any,
          value: p.vol!,
          color: p.yes > 0.5 ? "rgba(0,245,160,0.2)" : "rgba(255,71,87,0.2)",
        }))
        .sort((a: any, b: any) => a.time - b.time);

      if (volData.length > 0) {
        const volSer = chart.addHistogramSeries({
          priceFormat: { type: "volume" },
          priceScaleId: "vol",
        });
        volSer.setData(volData);
        chart.priceScale("vol").applyOptions({
          scaleMargins: { top: 0.85, bottom: 0 },
        });
      }

      chart.timeScale().fitContent();

      const handleResize = () => {
        if (containerRef.current && chartRef.current) {
          chartRef.current.applyOptions({
            width: containerRef.current.clientWidth,
          });
        }
      };
      window.addEventListener("resize", handleResize);

      return () => {
        window.removeEventListener("resize", handleResize);
      };
    })();

    return () => {
      disposed = true;
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [polySeries, spotSeries, spotSymbol, height]);

  return (
    <div
      ref={containerRef}
      className="w-full rounded-lg overflow-hidden"
      style={{ height }}
    />
  );
}
