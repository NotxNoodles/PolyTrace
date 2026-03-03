"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import type { WalletProfile, WalletTradeEntry } from "@/types";
import { getWalletProfile, getWalletTrades } from "@/lib/api";

function Badge({ text, className }: { text: string; className: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${className}`}
    >
      {text}
    </span>
  );
}

export default function WalletPage() {
  const params = useParams();
  const address = params.address as string;
  const [profile, setProfile] = useState<WalletProfile | null>(null);
  const [trades, setTrades] = useState<WalletTradeEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!address) return;
    Promise.all([getWalletProfile(address), getWalletTrades(address)])
      .then(([p, t]) => {
        setProfile(p);
        setTrades(t);
      })
      .catch((e) => setError(e.message));
  }, [address]);

  if (error) {
    return (
      <div className="card border-accent-red/30 bg-accent-red/5 text-accent-red text-sm">
        {error}
      </div>
    );
  }

  if (!profile) {
    return <div className="text-gray-500">Loading wallet profile...</div>;
  }

  const classColors: Record<string, string> = {
    sniper: "bg-accent-red/15 text-accent-red",
    specialist: "bg-accent-purple/15 text-accent-purple",
    one_hit: "bg-accent-yellow/15 text-accent-yellow",
    unknown: "bg-surface-300 text-gray-400",
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="font-mono text-xl font-bold">
          {address.slice(0, 8)}...{address.slice(-6)}
        </h1>
        <Badge
          text={profile.classification}
          className={classColors[profile.classification] || classColors.unknown}
        />
        {profile.flagged && (
          <Badge text="Sybil Flagged" className="bg-accent-red/15 text-accent-red" />
        )}
        {profile.label && (
          <span className="text-sm text-gray-400">{profile.label}</span>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
        <div className="stat-card">
          <span className="stat-label">Total PnL</span>
          <span
            className={`stat-value ${
              profile.total_pnl >= 0 ? "text-accent-green" : "text-accent-red"
            }`}
          >
            ${profile.total_pnl.toLocaleString()}
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Win Rate</span>
          <span className="stat-value text-accent-blue">
            {(profile.win_rate * 100).toFixed(1)}%
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Total Trades</span>
          <span className="stat-value">{profile.total_trades}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Volume (USDC)</span>
          <span className="stat-value font-mono text-lg">
            ${profile.total_volume_usdc.toLocaleString()}
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-label">First Seen</span>
          <span className="text-sm text-gray-300">
            {profile.first_seen
              ? new Date(profile.first_seen).toLocaleDateString()
              : "—"}
          </span>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Positions */}
        <div className="card">
          <h2 className="mb-4 font-semibold">Open Positions</h2>
          <div className="space-y-2">
            {profile.positions.length === 0 && (
              <p className="text-sm text-gray-500">No open positions.</p>
            )}
            {profile.positions.map((p, i) => (
              <div
                key={i}
                className="flex items-center justify-between rounded-lg bg-surface-50 px-3 py-2"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm">{p.market || p.condition_id}</p>
                  <p className="text-xs text-gray-500">
                    {p.outcome} @ {p.avg_price.toFixed(2)}
                  </p>
                </div>
                <div className="text-right">
                  <p
                    className={`font-mono text-sm ${
                      p.cash_pnl >= 0 ? "text-accent-green" : "text-accent-red"
                    }`}
                  >
                    {p.cash_pnl >= 0 ? "+" : ""}
                    ${p.cash_pnl.toFixed(2)}
                  </p>
                  <p className="font-mono text-xs text-gray-500">
                    {p.percent_pnl >= 0 ? "+" : ""}
                    {(p.percent_pnl * 100).toFixed(1)}%
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent Alerts */}
        <div className="card">
          <h2 className="mb-4 font-semibold">Recent Alerts</h2>
          <div className="space-y-2">
            {profile.recent_alerts.length === 0 && (
              <p className="text-sm text-gray-500">No recent alerts.</p>
            )}
            {profile.recent_alerts.map((a, i) => (
              <div
                key={i}
                className="rounded-lg border border-surface-300 bg-surface-50 p-3"
              >
                <div className="flex items-center gap-2">
                  <Badge
                    text={a.type}
                    className={classColors[a.type] || classColors.unknown}
                  />
                  <span className="font-mono text-xs text-gray-500">
                    {(a.confidence * 100).toFixed(0)}% conf
                  </span>
                </div>
                <p className="mt-1 text-xs text-gray-400">{a.description}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Trade History */}
      <div className="card overflow-x-auto p-0">
        <div className="px-4 py-3 border-b border-surface-300">
          <h2 className="font-semibold">Trade History</h2>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-surface-300 text-left text-xs uppercase tracking-wider text-gray-500">
              <th className="px-4 py-3">Side</th>
              <th className="px-4 py-3">Market</th>
              <th className="px-4 py-3 text-right">Price</th>
              <th className="px-4 py-3 text-right">Size (USDC)</th>
              <th className="px-4 py-3 text-right">Time</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-300">
            {trades.map((t) => (
              <tr key={t.id} className="hover:bg-surface-50 transition-colors">
                <td className="px-4 py-3">
                  <span
                    className={`font-mono text-xs font-bold ${
                      t.side === "BUY" ? "text-accent-green" : "text-accent-red"
                    }`}
                  >
                    {t.side}
                  </span>
                </td>
                <td className="max-w-[180px] truncate px-4 py-3">
                  {t.market || t.condition_id}
                </td>
                <td className="px-4 py-3 text-right font-mono">
                  {t.price.toFixed(3)}
                </td>
                <td className="px-4 py-3 text-right font-mono">
                  ${t.usdc_size.toLocaleString()}
                </td>
                <td className="px-4 py-3 text-right text-xs text-gray-500">
                  {new Date(t.timestamp).toLocaleString()}
                </td>
              </tr>
            ))}
            {trades.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                  No trades recorded.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
