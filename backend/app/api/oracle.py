"""Oracle Divergence API — signals, price overlays, and DAC metrics."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import (
    Market,
    MarketPrice,
    OracleSignal,
    SignalType,
    SpotPrice,
)

router = APIRouter(prefix="/oracle", tags=["Oracle"])


@router.get("/signals")
async def get_signals(
    signal_type: Optional[str] = Query(None, description="bullish_lead | bearish_lead | noise"),
    hours: int = Query(24, ge=1, le=720),
    min_dac: float = Query(0.0, ge=0.0),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """Fetch oracle signals with optional filters."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    q = (
        select(OracleSignal)
        .where(
            OracleSignal.timestamp >= cutoff,
            OracleSignal.dac_score >= min_dac,
        )
    )

    if signal_type:
        try:
            q = q.where(OracleSignal.signal_type == SignalType(signal_type))
        except ValueError:
            pass

    q = q.order_by(OracleSignal.dac_score.desc()).limit(limit).offset(offset)
    result = await session.execute(q)
    signals = result.scalars().all()

    enriched = []
    for s in signals:
        m_r = await session.execute(
            select(Market.question, Market.slug, Market.end_date).where(
                Market.condition_id == s.condition_id
            )
        )
        m = m_r.first()
        enriched.append(
            {
                "id": s.id,
                "condition_id": s.condition_id,
                "market": m.question if m else None,
                "slug": m.slug if m else None,
                "end_date": m.end_date.isoformat() if m and m.end_date else None,
                "spot_symbol": s.spot_symbol,
                "poly_delta_p": s.poly_delta_p,
                "spot_delta_s": s.spot_delta_s,
                "dac_score": s.dac_score,
                "ttr_hours": s.ttr_hours,
                "volume_surge": s.volume_surge_ratio,
                "signal": s.signal_type.value,
                "timestamp": s.timestamp.isoformat(),
            }
        )

    return enriched


@router.get("/divergence/{condition_id}")
async def get_divergence_overlay(
    condition_id: str,
    spot_symbol: str = Query(..., description="e.g. BTCUSDT, SPY, GC=F"),
    hours: int = Query(48, ge=1, le=720),
    session: AsyncSession = Depends(get_session),
):
    """Overlay data: Polymarket prices + spot prices for a market/symbol pair.

    Returns two aligned time-series for charting.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    poly_r = await session.execute(
        select(MarketPrice)
        .where(
            MarketPrice.condition_id == condition_id,
            MarketPrice.timestamp >= cutoff,
        )
        .order_by(MarketPrice.timestamp.asc())
    )
    poly_prices = poly_r.scalars().all()

    spot_r = await session.execute(
        select(SpotPrice)
        .where(
            SpotPrice.symbol == spot_symbol,
            SpotPrice.timestamp >= cutoff,
        )
        .order_by(SpotPrice.timestamp.asc())
    )
    spot_prices = spot_r.scalars().all()

    m_r = await session.execute(
        select(Market.question, Market.end_date).where(
            Market.condition_id == condition_id
        )
    )
    market = m_r.first()

    return {
        "condition_id": condition_id,
        "market": market.question if market else None,
        "end_date": market.end_date.isoformat() if market and market.end_date else None,
        "spot_symbol": spot_symbol,
        "poly_series": [
            {
                "t": p.timestamp.isoformat(),
                "yes": p.yes_price,
                "no": p.no_price,
                "vol": p.volume,
            }
            for p in poly_prices
        ],
        "spot_series": [
            {
                "t": s.timestamp.isoformat(),
                "o": s.open,
                "h": s.high,
                "l": s.low,
                "c": s.close,
                "vol": s.volume,
            }
            for s in spot_prices
        ],
    }


@router.get("/stats")
async def get_oracle_stats(
    session: AsyncSession = Depends(get_session),
):
    """Aggregate oracle statistics."""
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)

    total_r = await session.execute(
        select(func.count(OracleSignal.id)).where(
            OracleSignal.timestamp >= day_ago,
            OracleSignal.signal_type != SignalType.NOISE,
        )
    )
    total_signals = total_r.scalar_one()

    avg_dac_r = await session.execute(
        select(func.avg(OracleSignal.dac_score)).where(
            OracleSignal.timestamp >= day_ago,
            OracleSignal.signal_type != SignalType.NOISE,
        )
    )
    avg_dac = avg_dac_r.scalar_one() or 0.0

    by_symbol_r = await session.execute(
        select(
            OracleSignal.spot_symbol,
            func.count(OracleSignal.id),
        )
        .where(
            OracleSignal.timestamp >= day_ago,
            OracleSignal.signal_type != SignalType.NOISE,
        )
        .group_by(OracleSignal.spot_symbol)
    )
    by_symbol = {row[0]: row[1] for row in by_symbol_r.all()}

    return {
        "actionable_signals_24h": total_signals,
        "avg_dac_score": round(avg_dac, 4),
        "by_symbol": by_symbol,
    }
