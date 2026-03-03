"""Oracle Engine — Lead-Lag Spot Correlation.

Compares Polymarket probability movements against spot market price changes
to detect when prediction markets *lead* traditional markets.

For each crypto-linked Polymarket market, we:
  1. Pull recent market_prices (ΔP over 1h, 4h, 24h windows).
  2. Pull corresponding spot_prices for the mapped symbol.
  3. Compute the Decay Adjusted Confidence (DAC) score.
  4. Check if the poly ΔP *preceded* the spot ΔS by a configurable lag.
  5. Store actionable signals into `oracle_signals`.

Symbol mapping is keyword-based: if a market question mentions "Bitcoin" or
"BTC", we correlate against BTCUSDT; "Ethereum"/"ETH" -> ETHUSDT; "SOL" ->
SOLUSDT; "S&P"/"SPY" -> SPY; "Gold" -> GC=F; "Oil" -> CL=F.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session
from app.db.models import (
    Market,
    MarketPrice,
    OracleSignal,
    SignalType,
    SpotPrice,
)
from app.engines.decay_confidence import DACParams, compute_dac

logger = logging.getLogger(__name__)

KEYWORD_MAP: dict[str, str] = {
    "bitcoin": "BTCUSDT",
    "btc": "BTCUSDT",
    "ethereum": "ETHUSDT",
    "eth": "ETHUSDT",
    "solana": "SOLUSDT",
    "sol": "SOLUSDT",
    "s&p": "SPY",
    "spy": "SPY",
    "sp500": "SPY",
    "gold": "GC=F",
    "oil": "CL=F",
    "crude": "CL=F",
}

LOOKBACK_HOURS = 4
LAG_WINDOWS = [1, 4, 24]  # hours


def _map_to_spot(question: str) -> str | None:
    """Extract a spot symbol from a market question using keyword matching."""
    q_lower = (question or "").lower()
    for keyword, symbol in KEYWORD_MAP.items():
        if keyword in q_lower:
            return symbol
    return None


async def _get_price_change(
    session: AsyncSession,
    condition_id: str,
    window_hours: int,
    now: datetime,
) -> tuple[float, float, float] | None:
    """Return (price_now, price_prev, volume_in_window) for a market."""
    result_now = await session.execute(
        select(MarketPrice)
        .where(MarketPrice.condition_id == condition_id)
        .order_by(MarketPrice.timestamp.desc())
        .limit(1)
    )
    latest = result_now.scalar_one_or_none()
    if not latest:
        return None

    window_start = now - timedelta(hours=window_hours)
    result_prev = await session.execute(
        select(MarketPrice)
        .where(
            MarketPrice.condition_id == condition_id,
            MarketPrice.timestamp <= window_start,
        )
        .order_by(MarketPrice.timestamp.desc())
        .limit(1)
    )
    prev = result_prev.scalar_one_or_none()
    if not prev:
        return None

    vol_result = await session.execute(
        select(func.coalesce(func.sum(MarketPrice.volume), 0.0)).where(
            MarketPrice.condition_id == condition_id,
            MarketPrice.timestamp >= window_start,
        )
    )
    volume = vol_result.scalar_one() or 0.0

    return (latest.yes_price, prev.yes_price, volume)


async def _get_spot_change(
    session: AsyncSession,
    symbol: str,
    window_hours: int,
    now: datetime,
) -> float | None:
    """Percentage change in spot price over the window."""
    result_now = await session.execute(
        select(SpotPrice)
        .where(SpotPrice.symbol == symbol)
        .order_by(SpotPrice.timestamp.desc())
        .limit(1)
    )
    latest = result_now.scalar_one_or_none()
    if not latest:
        return None

    window_start = now - timedelta(hours=window_hours)
    result_prev = await session.execute(
        select(SpotPrice)
        .where(
            SpotPrice.symbol == symbol,
            SpotPrice.timestamp <= window_start,
        )
        .order_by(SpotPrice.timestamp.desc())
        .limit(1)
    )
    prev = result_prev.scalar_one_or_none()
    if not prev or prev.close == 0:
        return None

    return (latest.close - prev.close) / prev.close


async def _get_avg_volume(
    session: AsyncSession,
    condition_id: str,
    days: int = 7,
) -> float:
    """Average hourly volume over the past N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await session.execute(
        select(func.coalesce(func.avg(MarketPrice.volume), 0.0)).where(
            MarketPrice.condition_id == condition_id,
            MarketPrice.timestamp >= cutoff,
        )
    )
    return result.scalar_one() or 1.0


async def run_oracle() -> dict[str, int]:
    """Scan all crypto-linked markets for lead-lag divergences."""
    now = datetime.now(timezone.utc)
    stats = {"scanned": 0, "signals": 0}

    async with async_session() as session:
        result = await session.execute(
            select(Market).where(
                Market.active.is_(True),
                Market.end_date.isnot(None),
                Market.end_date > now,
            )
        )
        markets = result.scalars().all()

    async with async_session() as session:
        for market in markets:
            spot_symbol = _map_to_spot(market.question)
            if not spot_symbol:
                continue

            stats["scanned"] += 1

            for window in LAG_WINDOWS:
                poly_data = await _get_price_change(
                    session, market.condition_id, window, now
                )
                if not poly_data:
                    continue

                p_now, p_prev, vol_window = poly_data
                spot_delta = await _get_spot_change(session, spot_symbol, window, now)
                if spot_delta is None:
                    continue

                avg_vol = await _get_avg_volume(session, market.condition_id)
                ttr_hours = max(
                    (market.end_date - now).total_seconds() / 3600, 0
                )

                dac_result = compute_dac(
                    price_now=p_now,
                    price_prev=p_prev,
                    current_volume=vol_window,
                    avg_volume=avg_vol,
                    end_date=market.end_date,
                    now=now,
                )

                # Detect lead: poly moved, spot hasn't caught up yet
                poly_direction = 1 if dac_result.delta_p > 0 else -1
                spot_direction = 1 if spot_delta > 0 else -1

                if dac_result.dac_score < DACParams().noise_ceiling:
                    sig_type = SignalType.NOISE
                elif poly_direction != spot_direction and abs(dac_result.delta_p) > abs(spot_delta):
                    # Divergence: poly leads in opposite direction
                    sig_type = (
                        SignalType.BULLISH_LEAD
                        if poly_direction > 0
                        else SignalType.BEARISH_LEAD
                    )
                elif poly_direction == spot_direction and abs(dac_result.delta_p) > 2 * abs(spot_delta):
                    # Poly moved much more aggressively — still leading
                    sig_type = (
                        SignalType.BULLISH_LEAD
                        if poly_direction > 0
                        else SignalType.BEARISH_LEAD
                    )
                else:
                    sig_type = SignalType.NOISE

                if sig_type == SignalType.NOISE:
                    continue

                # Deduplicate: one signal per (market, symbol, window) per hour
                exists = await session.execute(
                    select(OracleSignal.id).where(
                        OracleSignal.condition_id == market.condition_id,
                        OracleSignal.spot_symbol == spot_symbol,
                        OracleSignal.timestamp >= now - timedelta(hours=1),
                    )
                )
                if exists.scalar_one_or_none():
                    continue

                session.add(
                    OracleSignal(
                        condition_id=market.condition_id,
                        spot_symbol=spot_symbol,
                        poly_delta_p=round(dac_result.delta_p, 6),
                        spot_delta_s=round(spot_delta, 6),
                        dac_score=round(dac_result.dac_score, 6),
                        ttr_hours=round(ttr_hours, 2),
                        volume_surge_ratio=round(dac_result.volume_surge, 4),
                        signal_type=sig_type,
                        timestamp=now,
                    )
                )
                stats["signals"] += 1

        await session.commit()

    logger.info("Oracle scan complete: %s", stats)
    return stats
