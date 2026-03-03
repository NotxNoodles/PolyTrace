const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

async function fetchJSON<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(`${API_BASE}${path}`);
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  }

  const res = await fetch(url.toString(), {
    next: { revalidate: 30 },
    headers: { Accept: "application/json" },
  });

  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }

  return res.json() as Promise<T>;
}

// ── Smart Money ──────────────────────────────────────────

import type {
  SmartMoneyAlert,
  SmartMoneyStats,
  WalletProfile,
  WalletTradeEntry,
  LeaderboardEntry,
  OracleSignal,
  OracleStats,
  DivergenceOverlay,
} from "@/types";

export async function getSmartMoneyAlerts(
  params?: Record<string, string>
): Promise<SmartMoneyAlert[]> {
  return fetchJSON("/smart-money/alerts", params);
}

export async function getSmartMoneyFeed(
  limit = 20
): Promise<SmartMoneyAlert[]> {
  return fetchJSON("/smart-money/feed", { limit: String(limit) });
}

export async function getSmartMoneyStats(): Promise<SmartMoneyStats> {
  return fetchJSON("/smart-money/stats");
}

// ── Wallet ───────────────────────────────────────────────

export async function getWalletProfile(address: string): Promise<WalletProfile> {
  return fetchJSON(`/wallet/${address}/profile`);
}

export async function getWalletTrades(
  address: string,
  params?: Record<string, string>
): Promise<WalletTradeEntry[]> {
  return fetchJSON(`/wallet/${address}/trades`, params);
}

export async function getLeaderboard(
  sortBy = "total_pnl"
): Promise<LeaderboardEntry[]> {
  return fetchJSON("/wallet/leaderboard", { sort_by: sortBy });
}

// ── Oracle ───────────────────────────────────────────────

export async function getOracleSignals(
  params?: Record<string, string>
): Promise<OracleSignal[]> {
  return fetchJSON("/oracle/signals", params);
}

export async function getDivergenceOverlay(
  conditionId: string,
  spotSymbol: string,
  hours = 48
): Promise<DivergenceOverlay> {
  return fetchJSON(`/oracle/divergence/${conditionId}`, {
    spot_symbol: spotSymbol,
    hours: String(hours),
  });
}

export async function getOracleStats(): Promise<OracleStats> {
  return fetchJSON("/oracle/stats");
}
