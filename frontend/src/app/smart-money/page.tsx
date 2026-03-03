"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { SmartMoneyAlert, SmartMoneyStats } from "@/types";
import { getSmartMoneyAlerts, getSmartMoneyStats } from "@/lib/api";

function AlertBadge({ type }: { type: string }) {
  const cls = `badge-${type}`;
  const labels: Record<string, string> = {
    sniper: "Sniper",
    specialist: "Specialist",
    one_hit: "One-Hit",
  };
  return <span className={cls}>{labels[type] || type}</span>;
}

export default function SmartMoneyPage() {
  const [alerts, setAlerts] = useState<SmartMoneyAlert[]>([]);
  const [stats, setStats] = useState<SmartMoneyStats | null>(null);
  const [filter, setFilter] = useState<string>("all");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params: Record<string, string> = { hours: "72", limit: "100" };
    if (filter !== "all") params.alert_type = filter;

    Promise.all([getSmartMoneyAlerts(params), getSmartMoneyStats()])
      .then(([a, s]) => {
        setAlerts(a);
        setStats(s);
      })
      .catch((e) => setError(e.message));
  }, [filter]);

  const filters = [
    { value: "all", label: "All" },
    { value: "sniper", label: "Snipers" },
    { value: "specialist", label: "Specialists" },
    { value: "one_hit", label: "One-Hit" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Smart Money Tracker</h1>
        <p className="mt-1 text-sm text-gray-500">
          Classified wallet alerts from the Heuristics Engine.
        </p>
      </div>

      {error && (
        <div className="card border-accent-red/30 bg-accent-red/5 text-accent-red text-sm">
          {error}
        </div>
      )}

      {/* Stats Row */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="stat-card">
          <span className="stat-label">Alerts (24h)</span>
          <span className="stat-value text-accent-green">
            {stats?.alerts_24h ?? "—"}
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Snipers</span>
          <span className="stat-value text-accent-red">
            {stats?.by_type?.sniper ?? 0}
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Tracked</span>
          <span className="stat-value text-accent-blue">
            {stats?.tracked_wallets ?? "—"}
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Sybil Flagged</span>
          <span className="stat-value text-accent-yellow">
            {stats?.flagged_sybil ?? 0}
          </span>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        {filters.map((f) => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={`rounded-lg px-3 py-1.5 text-sm transition-colors ${
              filter === f.value
                ? "bg-accent-green/15 text-accent-green"
                : "bg-surface-200 text-gray-400 hover:text-gray-200"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Alerts Table */}
      <div className="card overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-surface-300 text-left text-xs uppercase tracking-wider text-gray-500">
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Wallet</th>
              <th className="px-4 py-3">Market</th>
              <th className="px-4 py-3 text-right">USDC Vol</th>
              <th className="px-4 py-3 text-right">Confidence</th>
              <th className="px-4 py-3 text-right">Time</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-300">
            {alerts.map((a) => (
              <tr key={a.id} className="hover:bg-surface-50 transition-colors">
                <td className="px-4 py-3">
                  <AlertBadge type={a.type} />
                </td>
                <td className="px-4 py-3 font-mono text-xs">
                  <Link
                    href={`/wallet/${a.wallet}`}
                    className="text-accent-blue hover:underline"
                  >
                    {a.wallet.slice(0, 6)}...{a.wallet.slice(-4)}
                  </Link>
                </td>
                <td className="max-w-[200px] truncate px-4 py-3">
                  {a.market || a.condition_id.slice(0, 16) + "..."}
                </td>
                <td className="px-4 py-3 text-right font-mono text-accent-green">
                  ${a.usdc_volume?.toLocaleString()}
                </td>
                <td className="px-4 py-3 text-right font-mono">
                  {(a.confidence * 100).toFixed(1)}%
                </td>
                <td className="px-4 py-3 text-right text-xs text-gray-500">
                  {new Date(a.timestamp).toLocaleString()}
                </td>
              </tr>
            ))}
            {alerts.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                  No alerts match the current filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
