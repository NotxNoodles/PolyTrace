"""Poll the Polymarket Data API for trades, holders, and activity.

Data API base: https://data-api.polymarket.com  (public, no auth).
We focus on:
  - GET /trades?market={conditionId}   -> wallet_trades
  - GET /holders?market={conditionId}  -> wallet tracking + wallet_positions
  - GET /activity?user={address}       -> enrichment for flagged wallets
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
from app.db.models import (
    Market,
    Wallet,
    WalletTrade,
    WalletPosition,
    TradeSide,
)

logger = logging.getLogger(__name__)

BASE = settings.data_api_url
TRADES_LIMIT = 500
HOLDERS_LIMIT = 100
MARKETS_PER_RUN = 15


# ── Trades ───────────────────────────────────────────────


async def _fetch_trades(
    client: httpx.AsyncClient,
    condition_id: str,
    *,
    limit: int = TRADES_LIMIT,
    offset: int = 0,
) -> list[dict[str, Any]]:
    resp = await client.get(
        f"{BASE}/trades",
        params={
            "market": condition_id,
            "limit": limit,
            "offset": offset,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json() if isinstance(resp.json(), list) else resp.json().get("data", [])


async def _store_trades(
    session: AsyncSession, trades: list[dict[str, Any]]
) -> int:
    count = 0
    for t in trades:
        wallet = (t.get("user") or t.get("proxyWallet") or "").lower()
        if not wallet:
            continue

        ts_raw = t.get("timestamp") or t.get("matchTime")
        if isinstance(ts_raw, (int, float)):
            dt = datetime.fromtimestamp(ts_raw, tz=timezone.utc)
        elif isinstance(ts_raw, str):
            try:
                dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            except ValueError:
                continue
        else:
            continue

        tx_hash = t.get("transactionHash", "")

        if tx_hash:
            exists = await session.execute(
                select(WalletTrade.id).where(
                    WalletTrade.tx_hash == tx_hash,
                    WalletTrade.wallet_address == wallet,
                )
            )
            if exists.scalar_one_or_none():
                continue

        side_raw = (t.get("side") or "BUY").upper()
        side = TradeSide.BUY if side_raw == "BUY" else TradeSide.SELL

        session.add(
            WalletTrade(
                wallet_address=wallet,
                condition_id=t.get("market") or t.get("conditionId", ""),
                side=side,
                price=_f(t.get("price")),
                size=_f(t.get("size")),
                usdc_size=_f(t.get("usdcSize") or t.get("cashSize", 0)),
                timestamp=dt,
                tx_hash=tx_hash,
            )
        )
        await _ensure_wallet(session, wallet, dt)
        count += 1

    return count


# ── Holders ──────────────────────────────────────────────


async def _fetch_holders(
    client: httpx.AsyncClient,
    condition_id: str,
) -> list[dict[str, Any]]:
    resp = await client.get(
        f"{BASE}/holders",
        params={
            "market": condition_id,
            "limit": HOLDERS_LIMIT,
        },
        timeout=30,
    )
    resp.raise_for_status()
    raw = resp.json()
    return raw if isinstance(raw, list) else raw.get("data", [])


async def _store_holders(
    session: AsyncSession,
    condition_id: str,
    holders: list[dict[str, Any]],
) -> int:
    count = 0
    for h in holders:
        wallet = (h.get("address") or h.get("proxyWallet") or "").lower()
        if not wallet:
            continue

        result = await session.execute(
            select(WalletPosition).where(
                WalletPosition.wallet_address == wallet,
                WalletPosition.condition_id == condition_id,
            )
        )
        existing = result.scalar_one_or_none()

        pos_data = {
            "wallet_address": wallet,
            "condition_id": condition_id,
            "size": _f(h.get("size") or h.get("balance", 0)),
            "avg_price": _f(h.get("avgPrice", 0)),
            "current_value": _f(h.get("currentValue", 0)),
            "cash_pnl": _f(h.get("cashPnl", 0)),
            "percent_pnl": _f(h.get("percentPnl", 0)),
            "outcome": h.get("outcome"),
        }

        if existing:
            for k, v in pos_data.items():
                setattr(existing, k, v)
        else:
            session.add(WalletPosition(**pos_data))

        await _ensure_wallet(session, wallet)
        count += 1

    return count


# ── Activity (on-demand for specific wallets) ────────────


async def fetch_wallet_activity(
    address: str,
    *,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Fetch a single wallet's activity feed.  Used by the heuristics engine."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE}/activity",
            params={"user": address, "limit": limit, "sortBy": "TIMESTAMP"},
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json()
        return raw if isinstance(raw, list) else raw.get("data", [])


async def fetch_wallet_positions(
    address: str,
) -> list[dict[str, Any]]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE}/positions",
            params={"user": address, "limit": 500},
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json()
        return raw if isinstance(raw, list) else raw.get("data", [])


# ── Helpers ──────────────────────────────────────────────


async def _ensure_wallet(
    session: AsyncSession,
    address: str,
    seen_at: datetime | None = None,
) -> None:
    result = await session.execute(
        select(Wallet).where(Wallet.address == address)
    )
    w = result.scalar_one_or_none()
    if not w:
        session.add(
            Wallet(
                address=address,
                first_seen=seen_at or datetime.now(timezone.utc),
                last_seen=seen_at or datetime.now(timezone.utc),
            )
        )
    elif seen_at and (w.last_seen is None or seen_at > w.last_seen):
        w.last_seen = seen_at


def _f(val: Any) -> float:
    try:
        return float(val) if val is not None else 0.0
    except (ValueError, TypeError):
        return 0.0


# ── Main Orchestrator ────────────────────────────────────


async def poll_data_api() -> dict[str, int]:
    """Poll trades + holders for the top markets.  Returns counts."""
    async with async_session() as session:
        result = await session.execute(
            select(Market)
            .where(Market.active.is_(True))
            .order_by(Market.volume.desc().nulls_last())
            .limit(MARKETS_PER_RUN)
        )
        markets = result.scalars().all()

    stats = {"trades": 0, "holders": 0}

    async with httpx.AsyncClient() as client:
        for market in markets:
            cid = market.condition_id
            try:
                trades = await _fetch_trades(client, cid)
                async with async_session() as session:
                    stats["trades"] += await _store_trades(session, trades)
                    await session.commit()
            except Exception as exc:
                logger.warning("Data API trades error for %s: %s", cid[:16], exc)

            try:
                holders = await _fetch_holders(client, cid)
                async with async_session() as session:
                    stats["holders"] += await _store_holders(session, cid, holders)
                    await session.commit()
            except Exception as exc:
                logger.warning("Data API holders error for %s: %s", cid[:16], exc)

    logger.info("Data API poll complete: %s", stats)
    return stats
