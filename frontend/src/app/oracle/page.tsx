"use client";

import { useEffect, useState } from "react";
import type { OracleSignal, OracleStats } from "@/types";
import { getOracleSignals, getOracleStats } from "@/lib/api";
import OracleDivergenceScanner from "@/components/OracleDivergenceScanner";

export default function OraclePage() {
  const [signals, setSignals] = useState<OracleSignal[]>([]);
  const [stats, setStats] = useState<OracleStats | null>(null);
  const [selectedSignal, setSelectedSignal] = useState<OracleSignal | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      getOracleSignals({ hours: "72", limit: "50", min_dac: "0.01" }),
      getOracleStats(),
    ])
      .then(([s, st]) => {
        setSignals(s);
        setStats(st);
        if (s.length > 0) setSelectedSignal(s[0]);
      })
      .catch((e) => setError(e.message));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Oracle Divergence Scanner
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Polymarket probability vs. spot market price overlay. Detect when
          prediction markets lead traditional order books.
        </p>
      </div>

      {error && (
        <div className="card border-accent-red/30 bg-accent-red/5 text-accent-red text-sm">
          {error}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <div className="stat-card">
          <span className="stat-label">Actionable Signals (24h)</span>
          <span className="stat-value text-accent-green">
            {stats?.actionable_signals_24h ?? "—"}
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Avg DAC Score</span>
          <span className="stat-value text-accent-blue">
            {stats?.avg_dac_score?.toFixed(4) ?? "—"}
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Symbols Tracked</span>
          <span className="stat-value text-accent-purple">
            {stats?.by_symbol ? Object.keys(stats.by_symbol).length : "—"}
          </span>
        </div>
      </div>

      {/* Chart + Signal List */}
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          {selectedSignal ? (
            <OracleDivergenceScanner
              conditionId={selectedSignal.condition_id}
              spotSymbol={selectedSignal.spot_symbol}
              market={selectedSignal.market || "Unknown Market"}
            />
          ) : (
            <div className="card flex h-[400px] items-center justify-center text-gray-500">
              Select a signal to view the divergence chart.
            </div>
          )}
        </div>

        <div className="card max-h-[600px] overflow-y-auto p-0">
          <div className="sticky top-0 border-b border-surface-300 bg-surface-100 px-4 py-3">
            <h2 className="font-semibold">Signals</h2>
          </div>
          <div className="divide-y divide-surface-300">
            {signals.map((s) => (
              <button
                key={s.id}
                onClick={() => setSelectedSignal(s)}
                className={`w-full px-4 py-3 text-left transition-colors hover:bg-surface-50 ${
                  selectedSignal?.id === s.id ? "bg-surface-50" : ""
                }`}
              >
                <div className="flex items-center justify-between">
                  <span
                    className={`text-xs font-bold ${
                      s.signal === "bullish_lead"
                        ? "text-accent-green"
                        : "text-accent-red"
                    }`}
                  >
                    {s.signal === "bullish_lead" ? "BULLISH" : "BEARISH"}
                  </span>
                  <span className="font-mono text-xs text-accent-blue">
                    DAC {s.dac_score.toFixed(4)}
                  </span>
                </div>
                <p className="mt-1 truncate text-sm">{s.market || s.condition_id}</p>
                <div className="mt-1 flex items-center gap-3 text-xs text-gray-500">
                  <span>{s.spot_symbol}</span>
                  <span>TTR: {s.ttr_hours.toFixed(1)}h</span>
                  <span>
                    ΔP: {s.poly_delta_p > 0 ? "+" : ""}
                    {(s.poly_delta_p * 100).toFixed(2)}%
                  </span>
                </div>
              </button>
            ))}
            {signals.length === 0 && (
              <div className="px-4 py-8 text-center text-sm text-gray-500">
                No signals yet.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
