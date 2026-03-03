"""Wallet Profiler API — PnL, win rate, positions, and trade history."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import (
    SmartMoneyAlert,
    Wallet,
    WalletPosition,
    WalletTrade,
    Market,
)

router = APIRouter(prefix="/wallet", tags=["Wallet"])


@router.get("/{address}/profile")
async def get_wallet_profile(
    address: str,
    session: AsyncSession = Depends(get_session),
):
    """Full wallet profile: classification, PnL, win rate, positions."""
    addr = address.lower()
    result = await session.execute(
        select(Wallet).where(Wallet.address == addr)
    )
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    pos_r = await session.execute(
        select(WalletPosition)
        .where(WalletPosition.wallet_address == addr)
        .order_by(WalletPosition.current_value.desc())
        .limit(20)
    )
    positions = pos_r.scalars().all()

    trade_count_r = await session.execute(
        select(func.count(WalletTrade.id)).where(
            WalletTrade.wallet_address == addr
        )
    )
    trade_count = trade_count_r.scalar_one()

    total_volume_r = await session.execute(
        select(func.coalesce(func.sum(WalletTrade.usdc_size), 0.0)).where(
            WalletTrade.wallet_address == addr
        )
    )
    total_volume = total_volume_r.scalar_one()

    alert_r = await session.execute(
        select(SmartMoneyAlert)
        .where(SmartMoneyAlert.wallet_address == addr)
        .order_by(SmartMoneyAlert.timestamp.desc())
        .limit(5)
    )
    recent_alerts = alert_r.scalars().all()

    enriched_positions = []
    for p in positions:
        m_r = await session.execute(
            select(Market.question, Market.slug).where(
                Market.condition_id == p.condition_id
            )
        )
        m = m_r.first()
        enriched_positions.append(
            {
                "condition_id": p.condition_id,
                "market": m.question if m else None,
                "slug": m.slug if m else None,
                "size": p.size,
                "avg_price": p.avg_price,
                "current_value": p.current_value,
                "cash_pnl": p.cash_pnl,
                "percent_pnl": p.percent_pnl,
                "outcome": p.outcome,
            }
        )

    return {
        "address": wallet.address,
        "label": wallet.label,
        "classification": wallet.classification.value,
        "total_pnl": wallet.total_pnl,
        "win_rate": wallet.win_rate,
        "total_trades": trade_count,
        "total_volume_usdc": total_volume,
        "tags_specialty": wallet.tags_specialty,
        "flagged": wallet.flagged,
        "first_seen": wallet.first_seen.isoformat() if wallet.first_seen else None,
        "last_seen": wallet.last_seen.isoformat() if wallet.last_seen else None,
        "positions": enriched_positions,
        "recent_alerts": [
            {
                "type": a.alert_type.value,
                "confidence": a.confidence,
                "description": a.description,
                "timestamp": a.timestamp.isoformat(),
            }
            for a in recent_alerts
        ],
    }


@router.get("/{address}/trades")
async def get_wallet_trades(
    address: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """Paginated trade history for a wallet."""
    addr = address.lower()
    result = await session.execute(
        select(WalletTrade)
        .where(WalletTrade.wallet_address == addr)
        .order_by(WalletTrade.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    trades = result.scalars().all()

    enriched = []
    for t in trades:
        m_r = await session.execute(
            select(Market.question, Market.slug).where(
                Market.condition_id == t.condition_id
            )
        )
        m = m_r.first()
        enriched.append(
            {
                "id": t.id,
                "condition_id": t.condition_id,
                "market": m.question if m else None,
                "side": t.side.value,
                "price": t.price,
                "size": t.size,
                "usdc_size": t.usdc_size,
                "timestamp": t.timestamp.isoformat(),
                "tx_hash": t.tx_hash,
            }
        )

    return enriched


@router.get("/leaderboard")
async def get_leaderboard(
    sort_by: str = Query("total_pnl", regex="^(total_pnl|win_rate|total_trades)$"),
    limit: int = Query(25, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Top wallets ranked by PnL, win rate, or trade count."""
    order_col = {
        "total_pnl": Wallet.total_pnl.desc(),
        "win_rate": Wallet.win_rate.desc(),
        "total_trades": Wallet.total_trades.desc(),
    }[sort_by]

    result = await session.execute(
        select(Wallet)
        .where(Wallet.total_trades >= 5)
        .order_by(order_col)
        .limit(limit)
    )
    wallets = result.scalars().all()

    return [
        {
            "address": w.address,
            "label": w.label,
            "classification": w.classification.value,
            "total_pnl": w.total_pnl,
            "win_rate": w.win_rate,
            "total_trades": w.total_trades,
            "flagged": w.flagged,
        }
        for w in wallets
    ]
