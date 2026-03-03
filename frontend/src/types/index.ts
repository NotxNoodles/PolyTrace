export interface SmartMoneyAlert {
  id: number;
  wallet: string;
  condition_id: string;
  type: "sniper" | "specialist" | "one_hit";
  confidence: number;
  usdc_volume: number;
  description: string;
  market?: string | null;
  slug?: string | null;
  timestamp: string;
}

export interface SmartMoneyStats {
  alerts_24h: number;
  by_type: Record<string, number>;
  tracked_wallets: number;
  flagged_sybil: number;
}

export interface WalletProfile {
  address: string;
  label: string | null;
  classification: string;
  total_pnl: number;
  win_rate: number;
  total_trades: number;
  total_volume_usdc: number;
  tags_specialty: Record<string, any> | null;
  flagged: boolean;
  first_seen: string | null;
  last_seen: string | null;
  positions: WalletPositionEntry[];
  recent_alerts: WalletAlertEntry[];
}

export interface WalletPositionEntry {
  condition_id: string;
  market: string | null;
  slug: string | null;
  size: number;
  avg_price: number;
  current_value: number;
  cash_pnl: number;
  percent_pnl: number;
  outcome: string | null;
}

export interface WalletAlertEntry {
  type: string;
  confidence: number;
  description: string;
  timestamp: string;
}

export interface WalletTradeEntry {
  id: number;
  condition_id: string;
  market: string | null;
  side: "BUY" | "SELL";
  price: number;
  size: number;
  usdc_size: number;
  timestamp: string;
  tx_hash: string | null;
}

export interface OracleSignal {
  id: number;
  condition_id: string;
  market: string | null;
  slug: string | null;
  end_date: string | null;
  spot_symbol: string;
  poly_delta_p: number;
  spot_delta_s: number;
  dac_score: number;
  ttr_hours: number;
  volume_surge: number;
  signal: "bullish_lead" | "bearish_lead" | "noise";
  timestamp: string;
}

export interface DivergenceOverlay {
  condition_id: string;
  market: string | null;
  end_date: string | null;
  spot_symbol: string;
  poly_series: PolyPricePoint[];
  spot_series: SpotPricePoint[];
}

export interface PolyPricePoint {
  t: string;
  yes: number;
  no: number;
  vol: number | null;
}

export interface SpotPricePoint {
  t: string;
  o: number;
  h: number;
  l: number;
  c: number;
  vol: number;
}

export interface OracleStats {
  actionable_signals_24h: number;
  avg_dac_score: number;
  by_symbol: Record<string, number>;
}

export interface LeaderboardEntry {
  address: string;
  label: string | null;
  classification: string;
  total_pnl: number;
  win_rate: number;
  total_trades: number;
  flagged: boolean;
}
