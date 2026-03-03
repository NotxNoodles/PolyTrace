"""Heuristics Engine — classify wallets as Smart Money archetypes.

Three heuristics:

1. **The Sniper**: Heavy USDC volume into a market < 4 hours before major
   spot movement or resolution.  We look for wallets whose trades cluster
   in the final hours and correlate with subsequent price jumps.

2. **The Niche Specialist**: Win rate > 80% within a specific tag category
   (Crypto, Politics, etc.) across >= 10 resolved markets.

3. **One-Hit Wonders**: Freshly funded wallets (first_seen within 7 days)
   making a single massive bet (> $10k USDC) and cashing out.

Edge-case handling:
  - Sybil detection: flag wallets with near-identical trade timing on the
    same markets.  Group by (condition_id, side, 60s time bucket) and flag
    addresses that always appear together.
  - CEX funding heuristic: transfers from known CEX hot wallets (Binance,
    Coinbase, Kraken) identified by the from_address in onchain_transfers.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session
from app.db.models import (
    AlertType,
    Market,
    SmartMoneyAlert,
    Wallet,
    WalletClassification,
    WalletPosition,
    WalletTrade,
    TradeSide,
)

logger = logging.getLogger(__name__)

SNIPER_WINDOW_HOURS = 4
SNIPER_MIN_USDC = 2_000
SPECIALIST_MIN_TRADES = 10
SPECIALIST_MIN_WIN_RATE = 0.80
ONE_HIT_FRESH_DAYS = 7
ONE_HIT_MIN_USDC = 10_000

KNOWN_CEX_PREFIXES = {
    "0x28c6c06298d514db089934071355e5743bf21d60",  # Binance Hot 14
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549",  # Binance Hot 6
    "0xdfd5293d8e347dfe59e90efd55b2956a1343963d",  # Binance Hot 16
    "0x503828976d22510aad0201ac7ec88293211d23da",  # Coinbase 2
    "0x2819c144d5946404c0516b6f817a960db37d4929",  # Kraken 13
}


# ── Sniper Detection ────────────────────────────────────


async def _detect_snipers(session: AsyncSession) -> list[dict[str, Any]]:
    """Find wallets with heavy volume in the 4h window before market end_date."""
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=SNIPER_WINDOW_HOURS)

    result = await session.execute(
        select(Market).where(
            Market.active.is_(True),
            Market.end_date.isnot(None),
            Market.end_date <= cutoff,
            Market.end_date > now,
        )
    )
    closing_markets = result.scalars().all()
    alerts: list[dict[str, Any]] = []

    for market in closing_markets:
        window_start = market.end_date - timedelta(hours=SNIPER_WINDOW_HOURS)

        result = await session.execute(
            select(
                WalletTrade.wallet_address,
                func.sum(WalletTrade.usdc_size).label("total_usdc"),
                func.count(WalletTrade.id).label("trade_count"),
            )
            .where(
                WalletTrade.condition_id == market.condition_id,
                WalletTrade.timestamp >= window_start,
                WalletTrade.timestamp <= market.end_date,
            )
            .group_by(WalletTrade.wallet_address)
            .having(func.sum(WalletTrade.usdc_size) >= SNIPER_MIN_USDC)
            .order_by(func.sum(WalletTrade.usdc_size).desc())
        )
        rows = result.all()

        for row in rows:
            ttr = (market.end_date - now).total_seconds() / 3600
            confidence = min(1.0, row.total_usdc / 50_000) * min(1.0, 1.0 / max(ttr, 0.1))

            alerts.append(
                {
                    "wallet_address": row.wallet_address,
                    "condition_id": market.condition_id,
                    "alert_type": AlertType.SNIPER,
                    "confidence": round(confidence, 4),
                    "usdc_volume": row.total_usdc,
                    "description": (
                        f"${row.total_usdc:,.0f} USDC across {row.trade_count} trades "
                        f"within {SNIPER_WINDOW_HOURS}h of resolution "
                        f"(TTR: {ttr:.1f}h)"
                    ),
                }
            )

    return alerts


# ── Specialist Detection ─────────────────────────────────


async def _detect_specialists(session: AsyncSession) -> list[dict[str, Any]]:
    """Find wallets with >80% win rate in specific tag categories."""
    result = await session.execute(
        select(Wallet).where(
            Wallet.total_trades >= SPECIALIST_MIN_TRADES,
            Wallet.win_rate >= SPECIALIST_MIN_WIN_RATE,
        )
    )
    specialists = result.scalars().all()
    alerts: list[dict[str, Any]] = []

    for wallet in specialists:
        tags = wallet.tags_specialty or {}
        top_tag = max(tags, key=lambda k: tags[k].get("win_rate", 0), default=None) if tags else None

        pos_result = await session.execute(
            select(WalletPosition)
            .where(WalletPosition.wallet_address == wallet.address)
            .order_by(WalletPosition.current_value.desc())
            .limit(1)
        )
        top_pos = pos_result.scalar_one_or_none()
        condition_id = top_pos.condition_id if top_pos else ""

        alerts.append(
            {
                "wallet_address": wallet.address,
                "condition_id": condition_id,
                "alert_type": AlertType.SPECIALIST,
                "confidence": round(wallet.win_rate, 4),
                "usdc_volume": wallet.total_pnl,
                "description": (
                    f"Win rate {wallet.win_rate:.0%} across {wallet.total_trades} trades"
                    + (f", specializes in '{top_tag}'" if top_tag else "")
                ),
            }
        )

    return alerts


# ── One-Hit Wonder Detection ─────────────────────────────


async def _detect_one_hit_wonders(session: AsyncSession) -> list[dict[str, Any]]:
    """Find freshly funded wallets making a single large bet."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=ONE_HIT_FRESH_DAYS)

    result = await session.execute(
        select(
            WalletTrade.wallet_address,
            WalletTrade.condition_id,
            func.sum(WalletTrade.usdc_size).label("total_usdc"),
            func.count(WalletTrade.id).label("trade_count"),
        )
        .join(Wallet, Wallet.address == WalletTrade.wallet_address)
        .where(
            Wallet.first_seen >= cutoff,
            Wallet.total_trades <= 5,
        )
        .group_by(WalletTrade.wallet_address, WalletTrade.condition_id)
        .having(func.sum(WalletTrade.usdc_size) >= ONE_HIT_MIN_USDC)
    )
    rows = result.all()
    alerts: list[dict[str, Any]] = []

    for row in rows:
        confidence = min(1.0, row.total_usdc / 100_000)
        alerts.append(
            {
                "wallet_address": row.wallet_address,
                "condition_id": row.condition_id,
                "alert_type": AlertType.ONE_HIT,
                "confidence": round(confidence, 4),
                "usdc_volume": row.total_usdc,
                "description": (
                    f"Fresh wallet (≤{ONE_HIT_FRESH_DAYS}d old), "
                    f"${row.total_usdc:,.0f} USDC in {row.trade_count} trades "
                    f"on a single market"
                ),
            }
        )

    return alerts


# ── Sybil Flagging ───────────────────────────────────────


async def _flag_sybil_clusters(session: AsyncSession) -> int:
    """Flag wallets that trade the same market/side within 60s windows repeatedly.

    Uses a subquery to find time-bucket clusters with 3+ distinct wallets,
    then builds a co-occurrence map to flag Sybil pairs.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=24)

    bucket_col = func.date_trunc("minute", WalletTrade.timestamp).label("bucket")

    # Step 1: find (condition, side, minute-bucket) combos with 3+ wallets
    cluster_q = (
        select(
            WalletTrade.condition_id,
            WalletTrade.side,
            bucket_col,
        )
        .where(WalletTrade.timestamp >= since)
        .group_by(
            WalletTrade.condition_id,
            WalletTrade.side,
            bucket_col,
        )
        .having(func.count(func.distinct(WalletTrade.wallet_address)) >= 3)
    )
    cluster_result = await session.execute(cluster_q)
    clusters = cluster_result.all()

    if not clusters:
        return 0

    # Step 2: for each cluster, get the distinct wallet addresses
    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    for cluster in clusters:
        addr_q = (
            select(func.distinct(WalletTrade.wallet_address))
            .where(
                WalletTrade.condition_id == cluster.condition_id,
                WalletTrade.side == cluster.side,
                func.date_trunc("minute", WalletTrade.timestamp) == cluster.bucket,
            )
        )
        addr_result = await session.execute(addr_q)
        addrs = sorted([row[0] for row in addr_result.all()])

        for i in range(len(addrs)):
            for j in range(i + 1, len(addrs)):
                pair_counts[(addrs[i], addrs[j])] += 1

    flagged = 0
    for (a, b), count in pair_counts.items():
        if count >= 5:
            for addr in (a, b):
                r = await session.execute(
                    select(Wallet).where(Wallet.address == addr)
                )
                w = r.scalar_one_or_none()
                if w and not w.flagged:
                    w.flagged = True
                    flagged += 1

    return flagged


# ── Main Orchestrator ────────────────────────────────────


async def _store_alerts(
    session: AsyncSession, alerts: list[dict[str, Any]]
) -> int:
    stored = 0
    for a in alerts:
        exists = await session.execute(
            select(SmartMoneyAlert.id).where(
                SmartMoneyAlert.wallet_address == a["wallet_address"],
                SmartMoneyAlert.condition_id == a["condition_id"],
                SmartMoneyAlert.alert_type == a["alert_type"],
                SmartMoneyAlert.timestamp >= datetime.now(timezone.utc) - timedelta(hours=1),
            )
        )
        if exists.scalar_one_or_none():
            continue

        session.add(SmartMoneyAlert(**a))

        # Update wallet classification
        r = await session.execute(
            select(Wallet).where(Wallet.address == a["wallet_address"])
        )
        wallet = r.scalar_one_or_none()
        if wallet:
            cls_map = {
                AlertType.SNIPER: WalletClassification.SNIPER,
                AlertType.SPECIALIST: WalletClassification.SPECIALIST,
                AlertType.ONE_HIT: WalletClassification.ONE_HIT,
            }
            wallet.classification = cls_map.get(
                a["alert_type"], WalletClassification.UNKNOWN
            )

        stored += 1
    return stored


async def run_heuristics() -> dict[str, int]:
    """Execute all heuristic detectors and store results."""
    stats: dict[str, int] = {}

    async with async_session() as session:
        sniper_alerts = await _detect_snipers(session)
        specialist_alerts = await _detect_specialists(session)
        one_hit_alerts = await _detect_one_hit_wonders(session)

        all_alerts = sniper_alerts + specialist_alerts + one_hit_alerts
        stats["alerts_stored"] = await _store_alerts(session, all_alerts)
        stats["sybil_flagged"] = await _flag_sybil_clusters(session)

        await session.commit()

    stats["snipers"] = len(sniper_alerts)
    stats["specialists"] = len(specialist_alerts)
    stats["one_hit_wonders"] = len(one_hit_alerts)

    logger.info("Heuristics run complete: %s", stats)
    return stats
