"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { SmartMoneyStats, OracleStats, SmartMoneyAlert } from "@/types";
import { getSmartMoneyStats, getOracleStats, getSmartMoneyFeed } from "@/lib/api";

function StatCard({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="stat-card">
      <span className="stat-label">{label}</span>
      <span className={`stat-value ${accent || "text-gray-100"}`}>{value}</span>
    </div>
  );
}

function AlertBadge({ type }: { type: string }) {
  const cls = `badge-${type}`;
  const labels: Record<string, string> = {
    sniper: "Sniper",
    specialist: "Specialist",
    one_hit: "One-Hit",
  };
  return <span className={cls}>{labels[type] || type}</span>;
}

export default function DashboardPage() {
  const [smStats, setSmStats] = useState<SmartMoneyStats | null>(null);
  const [oStats, setOStats] = useState<OracleStats | null>(null);
  const [feed, setFeed] = useState<SmartMoneyAlert[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getSmartMoneyStats(), getOracleStats(), getSmartMoneyFeed(10)])
      .then(([sm, o, f]) => {
        setSmStats(sm);
        setOStats(o);
        setFeed(f);
      })
      .catch((e) => setError(e.message));
  }, []);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">
          Real-time overview of Smart Money activity and Oracle signals.
        </p>
      </div>

      {error && (
        <div className="card border-accent-red/30 bg-accent-red/5 text-accent-red text-sm">
          Backend unavailable: {error}. Start the API server to see live data.
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard
          label="Alerts (24h)"
          value={smStats?.alerts_24h?.toString() ?? "—"}
          accent="text-accent-green"
        />
        <StatCard
          label="Tracked Wallets"
          value={smStats?.tracked_wallets?.toString() ?? "—"}
          accent="text-accent-blue"
        />
        <StatCard
          label="Oracle Signals (24h)"
          value={oStats?.actionable_signals_24h?.toString() ?? "—"}
          accent="text-accent-purple"
        />
        <StatCard
          label="Avg DAC Score"
          value={oStats?.avg_dac_score?.toFixed(4) ?? "—"}
          accent="text-accent-yellow"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Live Feed */}
        <div className="card">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-semibold">Live Smart Money Feed</h2>
            <Link
              href="/smart-money"
              className="text-xs text-accent-green hover:underline"
            >
              View all
            </Link>
          </div>
          <div className="space-y-3">
            {feed.length === 0 && !error && (
              <p className="text-sm text-gray-500">No alerts yet. Data will appear once the backend is running.</p>
            )}
            {feed.map((a) => (
              <div
                key={a.id}
                className="flex items-start gap-3 rounded-lg border border-surface-300 bg-surface-50 p-3"
              >
                <AlertBadge type={a.type} />
                <div className="flex-1 min-w-0">
                  <p className="truncate text-sm font-medium">
                    {a.market || a.condition_id}
                  </p>
                  <p className="text-xs text-gray-500">{a.description}</p>
                </div>
                <span className="shrink-0 font-mono text-xs text-accent-green">
                  ${a.usdc_volume?.toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Oracle Signal Breakdown */}
        <div className="card">
          <h2 className="mb-4 font-semibold">Oracle Signal Breakdown</h2>
          {oStats?.by_symbol && Object.keys(oStats.by_symbol).length > 0 ? (
            <div className="space-y-2">
              {Object.entries(oStats.by_symbol).map(([sym, count]) => (
                <div
                  key={sym}
                  className="flex items-center justify-between rounded-lg bg-surface-50 px-3 py-2"
                >
                  <span className="font-mono text-sm">{sym}</span>
                  <span className="font-mono text-sm text-accent-blue">
                    {count} signal{count !== 1 ? "s" : ""}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-500">
              No oracle signals yet. Data populates once the backend scans markets.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
