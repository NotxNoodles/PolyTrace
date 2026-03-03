"""Smart Money API routes — live alerts feed and filtered queries."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import AlertType, SmartMoneyAlert, Wallet, Market

router = APIRouter(prefix="/smart-money", tags=["Smart Money"])


@router.get("/alerts")
async def get_alerts(
    alert_type: Optional[str] = Query(None, description="sniper | specialist | one_hit"),
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """Get recent Smart Money alerts, optionally filtered by type."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    q = select(SmartMoneyAlert).where(SmartMoneyAlert.timestamp >= cutoff)

    if alert_type:
        try:
            q = q.where(SmartMoneyAlert.alert_type == AlertType(alert_type))
        except ValueError:
            pass

    q = q.order_by(SmartMoneyAlert.timestamp.desc()).limit(limit).offset(offset)
    result = await session.execute(q)
    alerts = result.scalars().all()

    return [
        {
            "id": a.id,
            "wallet": a.wallet_address,
            "condition_id": a.condition_id,
            "type": a.alert_type.value,
            "confidence": a.confidence,
            "usdc_volume": a.usdc_volume,
            "description": a.description,
            "timestamp": a.timestamp.isoformat(),
        }
        for a in alerts
    ]


@router.get("/feed")
async def get_live_feed(
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Real-time feed of the most recent alerts across all types."""
    result = await session.execute(
        select(SmartMoneyAlert)
        .order_by(SmartMoneyAlert.timestamp.desc())
        .limit(limit)
    )
    alerts = result.scalars().all()

    enriched = []
    for a in alerts:
        market_r = await session.execute(
            select(Market.question, Market.slug).where(
                Market.condition_id == a.condition_id
            )
        )
        market_info = market_r.first()

        enriched.append(
            {
                "id": a.id,
                "wallet": a.wallet_address,
                "type": a.alert_type.value,
                "confidence": a.confidence,
                "usdc_volume": a.usdc_volume,
                "description": a.description,
                "market": market_info.question if market_info else None,
                "slug": market_info.slug if market_info else None,
                "timestamp": a.timestamp.isoformat(),
            }
        )

    return enriched


@router.get("/stats")
async def get_stats(
    session: AsyncSession = Depends(get_session),
):
    """Aggregate stats for the Smart Money dashboard."""
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)

    total_r = await session.execute(
        select(func.count(SmartMoneyAlert.id)).where(
            SmartMoneyAlert.timestamp >= day_ago
        )
    )
    total_24h = total_r.scalar_one()

    by_type_r = await session.execute(
        select(
            SmartMoneyAlert.alert_type,
            func.count(SmartMoneyAlert.id),
        )
        .where(SmartMoneyAlert.timestamp >= day_ago)
        .group_by(SmartMoneyAlert.alert_type)
    )
    by_type = {row[0].value: row[1] for row in by_type_r.all()}

    tracked_r = await session.execute(
        select(func.count(Wallet.address)).where(
            Wallet.classification != "unknown"
        )
    )
    tracked_wallets = tracked_r.scalar_one()

    flagged_r = await session.execute(
        select(func.count(Wallet.address)).where(Wallet.flagged.is_(True))
    )
    flagged_wallets = flagged_r.scalar_one()

    return {
        "alerts_24h": total_24h,
        "by_type": by_type,
        "tracked_wallets": tracked_wallets,
        "flagged_sybil": flagged_wallets,
    }
