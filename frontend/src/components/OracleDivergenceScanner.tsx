"use client";

import { useEffect, useState } from "react";
import type { DivergenceOverlay } from "@/types";
import { getDivergenceOverlay } from "@/lib/api";
import PriceOverlayChart from "@/components/charts/PriceOverlayChart";
import DACGauge from "@/components/DACGauge";

interface Props {
  conditionId: string;
  spotSymbol: string;
  market: string;
}

export default function OracleDivergenceScanner({
  conditionId,
  spotSymbol,
  market,
}: Props) {
  const [data, setData] = useState<DivergenceOverlay | null>(null);
  const [hours, setHours] = useState(48);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getDivergenceOverlay(conditionId, spotSymbol, hours)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [conditionId, spotSymbol, hours]);

  const dacScore = computeClientDAC(data);

  return (
    <div className="card space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="truncate font-semibold">{market}</h3>
          <div className="mt-1 flex items-center gap-3 text-xs text-gray-500">
            <span className="font-mono text-accent-blue">{spotSymbol}</span>
            {data?.end_date && (
              <span>
                Resolves: {new Date(data.end_date).toLocaleDateString()}
              </span>
            )}
          </div>
        </div>

        {/* Time range selector */}
        <div className="flex gap-1">
          {[12, 24, 48, 168].map((h) => (
            <button
              key={h}
              onClick={() => setHours(h)}
              className={`rounded px-2 py-1 text-xs transition-colors ${
                hours === h
                  ? "bg-accent-green/15 text-accent-green"
                  : "bg-surface-200 text-gray-400 hover:text-gray-200"
              }`}
            >
              {h < 48 ? `${h}h` : `${h / 24}d`}
            </button>
          ))}
        </div>
      </div>

      {/* Chart Area */}
      {loading ? (
        <div className="flex h-[380px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent-green border-t-transparent" />
        </div>
      ) : error ? (
        <div className="flex h-[380px] items-center justify-center text-sm text-gray-500">
          {error}
        </div>
      ) : data ? (
        <PriceOverlayChart
          polySeries={data.poly_series}
          spotSeries={data.spot_series}
          spotSymbol={spotSymbol}
        />
      ) : null}

      {/* DAC Gauge + Stats */}
      <div className="grid gap-4 sm:grid-cols-3">
        <DACGauge
          score={dacScore.dac}
          ttrHours={dacScore.ttr}
          volumeSurge={dacScore.volSurge}
        />

        <div className="rounded-lg border border-surface-300 bg-surface-50 p-3">
          <span className="text-xs font-medium text-gray-400">
            Poly ΔP (window)
          </span>
          <p
            className={`mt-1 font-mono text-xl font-bold ${
              dacScore.deltaP >= 0 ? "text-accent-green" : "text-accent-red"
            }`}
          >
            {dacScore.deltaP >= 0 ? "+" : ""}
            {(dacScore.deltaP * 100).toFixed(2)}%
          </p>
        </div>

        <div className="rounded-lg border border-surface-300 bg-surface-50 p-3">
          <span className="text-xs font-medium text-gray-400">
            Spot ΔS (window)
          </span>
          <p
            className={`mt-1 font-mono text-xl font-bold ${
              dacScore.deltaS >= 0 ? "text-accent-green" : "text-accent-red"
            }`}
          >
            {dacScore.deltaS >= 0 ? "+" : ""}
            {(dacScore.deltaS * 100).toFixed(2)}%
          </p>
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-xs text-gray-500">
        <div className="flex items-center gap-1.5">
          <div className="h-0.5 w-4 rounded bg-accent-green" />
          <span>P(Yes) probability</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-0.5 w-4 rounded bg-accent-blue" style={{ borderStyle: "dashed" }} />
          <span>{spotSymbol} (normalized)</span>
        </div>
      </div>
    </div>
  );
}

function computeClientDAC(data: DivergenceOverlay | null) {
  const empty = { dac: 0, ttr: 0, volSurge: 0, deltaP: 0, deltaS: 0 };
  if (!data || data.poly_series.length < 2) return empty;

  const ps = data.poly_series;
  const first = ps[0];
  const last = ps[ps.length - 1];
  const deltaP = last.yes - first.yes;

  const ss = data.spot_series;
  let deltaS = 0;
  if (ss.length >= 2) {
    const sFirst = ss[0];
    const sLast = ss[ss.length - 1];
    deltaS = sFirst.c !== 0 ? (sLast.c - sFirst.c) / sFirst.c : 0;
  }

  let ttr = 0;
  if (data.end_date) {
    ttr = Math.max(
      (new Date(data.end_date).getTime() - Date.now()) / 3_600_000,
      0
    );
  }

  const vols = ps.filter((p) => p.vol != null).map((p) => p.vol!);
  const avgVol = vols.length > 0 ? vols.reduce((a, b) => a + b, 0) / vols.length : 1;
  const lastVol = vols.length > 0 ? vols[vols.length - 1] : 0;
  const volSurge = avgVol > 0 ? lastVol / avgVol : 0;

  const k = 0.15;
  const mid = 6;
  const decayW = 1 / (1 + Math.exp(-k * (ttr - mid)));
  const dac = Math.abs(deltaP) * Math.max(volSurge, 0.1) * decayW;

  return { dac, ttr, volSurge, deltaP, deltaS };
}
