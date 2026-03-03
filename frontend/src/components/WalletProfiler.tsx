"use client";

import { useEffect, useState } from "react";
import type { WalletProfile } from "@/types";
import { getWalletProfile } from "@/lib/api";

interface Props {
  address: string;
  compact?: boolean;
}

export default function WalletProfiler({ address, compact = false }: Props) {
  const [profile, setProfile] = useState<WalletProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getWalletProfile(address)
      .then(setProfile)
      .catch(() => setProfile(null))
      .finally(() => setLoading(false));
  }, [address]);

  if (loading) {
    return (
      <div className="card animate-pulse">
        <div className="h-4 w-32 rounded bg-surface-300" />
        <div className="mt-2 h-8 w-24 rounded bg-surface-300" />
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="card text-sm text-gray-500">
        Wallet not found: {address.slice(0, 10)}...
      </div>
    );
  }

  if (compact) {
    return (
      <div className="flex items-center gap-3 rounded-lg bg-surface-50 px-3 py-2">
        <div className="min-w-0 flex-1">
          <p className="truncate font-mono text-xs">{profile.address}</p>
          <p className="text-xs text-gray-500">{profile.classification}</p>
        </div>
        <span
          className={`font-mono text-sm font-bold ${
            profile.total_pnl >= 0 ? "text-accent-green" : "text-accent-red"
          }`}
        >
          ${profile.total_pnl.toLocaleString()}
        </span>
      </div>
    );
  }

  return (
    <div className="card space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-mono text-sm font-bold">
            {address.slice(0, 8)}...{address.slice(-6)}
          </h3>
          <span className={`badge-${profile.classification}`}>
            {profile.classification}
          </span>
        </div>
        {profile.flagged && (
          <span className="badge-sniper">Sybil</span>
        )}
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div>
          <p className="text-xs text-gray-500">PnL</p>
          <p
            className={`font-mono text-lg font-bold ${
              profile.total_pnl >= 0 ? "text-accent-green" : "text-accent-red"
            }`}
          >
            ${profile.total_pnl.toLocaleString()}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Win Rate</p>
          <p className="font-mono text-lg font-bold text-accent-blue">
            {(profile.win_rate * 100).toFixed(1)}%
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Trades</p>
          <p className="font-mono text-lg font-bold">{profile.total_trades}</p>
        </div>
      </div>

      {profile.positions.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-medium text-gray-500">
            Top Positions
          </p>
          {profile.positions.slice(0, 3).map((p, i) => (
            <div
              key={i}
              className="flex items-center justify-between border-t border-surface-300 py-2 first:border-0"
            >
              <span className="max-w-[180px] truncate text-xs">
                {p.market || p.condition_id}
              </span>
              <span
                className={`font-mono text-xs ${
                  p.cash_pnl >= 0 ? "text-accent-green" : "text-accent-red"
                }`}
              >
                {p.cash_pnl >= 0 ? "+" : ""}${p.cash_pnl.toFixed(2)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
