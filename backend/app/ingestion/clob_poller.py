"""Poll the Polymarket CLOB API for price history.

Uses GET /prices-history with the `market` param (= CLOB asset/token id).
Public endpoint, no auth required.  We store each candle into `market_prices`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import async_session
from app.db.models import Market, MarketPrice

logger = logging.getLogger(__name__)

BASE = settings.clob_api_url
BATCH_SIZE = 25  # markets per run to stay within rate limits


async def _fetch_price_history(
    client: httpx.AsyncClient,
    token_id: str,
    *,
    interval: str = "1h",
    fidelity: int = 5,
    start_ts: int | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "market": token_id,
        "interval": interval,
        "fidelity": fidelity,
    }
    if start_ts:
        params["startTs"] = start_ts

    resp = await client.get(
        f"{BASE}/prices-history",
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("history", [])


async def _get_latest_ts(session: AsyncSession, condition_id: str) -> int | None:
    """Get the latest stored timestamp for incremental ingestion."""
    result = await session.execute(
        select(func.max(MarketPrice.timestamp)).where(
            MarketPrice.condition_id == condition_id
        )
    )
    latest = result.scalar_one_or_none()
    if latest:
        return int(latest.timestamp())
    return None


async def _store_prices(
    session: AsyncSession,
    condition_id: str,
    history: list[dict[str, Any]],
) -> int:
    count = 0
    for point in history:
        ts = point.get("t")
        price = point.get("p")
        if ts is None or price is None:
            continue

        dt = datetime.fromtimestamp(ts, tz=timezone.utc)

        exists = await session.execute(
            select(MarketPrice.id).where(
                MarketPrice.condition_id == condition_id,
                MarketPrice.timestamp == dt,
            )
        )
        if exists.scalar_one_or_none():
            continue

        session.add(
            MarketPrice(
                condition_id=condition_id,
                timestamp=dt,
                yes_price=float(price),
                no_price=1.0 - float(price),
            )
        )
        count += 1

    return count


async def poll_clob_prices() -> int:
    """Fetch price history for the top-volume markets.  Returns rows inserted."""
    total = 0

    async with async_session() as session:
        result = await session.execute(
            select(Market)
            .where(Market.active.is_(True))
            .order_by(Market.volume.desc().nulls_last())
            .limit(BATCH_SIZE)
        )
        markets = result.scalars().all()

    async with httpx.AsyncClient() as client:
        for market in markets:
            clob_ids = (market.clob_token_ids or {}).get("ids", [])
            if not clob_ids:
                continue

            # Use the first token id (Yes token)
            token_id = clob_ids[0] if isinstance(clob_ids, list) else clob_ids

            async with async_session() as session:
                start_ts = await _get_latest_ts(session, market.condition_id)

            try:
                history = await _fetch_price_history(
                    client, token_id, start_ts=start_ts
                )
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "CLOB price-history %s: HTTP %s",
                    market.condition_id[:16],
                    exc.response.status_code,
                )
                continue
            except httpx.RequestError as exc:
                logger.warning("CLOB request error for %s: %s", market.condition_id[:16], exc)
                continue

            if not history:
                continue

            async with async_session() as session:
                inserted = await _store_prices(session, market.condition_id, history)
                await session.commit()
                total += inserted

            logger.debug(
                "CLOB prices: %s -> %d new candles",
                market.condition_id[:16],
                inserted,
            )

    logger.info("CLOB poll complete: %d price rows inserted", total)
    return total
