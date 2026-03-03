"""Ingest spot market data from Binance REST API and yfinance.

Binance: GET /api/v3/klines  (public, no auth, weight=2)
yfinance: SPY, GC=F (gold futures), CL=F (crude oil futures)

All data is stored into the `spot_prices` table as OHLCV candles.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import async_session
from app.db.models import SpotPrice

logger = logging.getLogger(__name__)

BINANCE_BASE = settings.binance_api_url

BINANCE_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
YFINANCE_TICKERS = ["SPY", "GC=F", "CL=F"]


# ── Binance ──────────────────────────────────────────────


async def _fetch_binance_klines(
    client: httpx.AsyncClient,
    symbol: str,
    *,
    interval: str = "1h",
    limit: int = 100,
) -> list[list[Any]]:
    resp = await client.get(
        f"{BINANCE_BASE}/api/v3/klines",
        params={"symbol": symbol, "interval": interval, "limit": limit},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


async def _store_klines(
    session: AsyncSession,
    symbol: str,
    klines: list[list[Any]],
) -> int:
    count = 0
    for k in klines:
        # Binance kline: [open_time, O, H, L, C, vol, close_time, ...]
        open_time_ms = k[0]
        dt = datetime.fromtimestamp(open_time_ms / 1000, tz=timezone.utc)

        exists = await session.execute(
            select(SpotPrice.id).where(
                SpotPrice.symbol == symbol,
                SpotPrice.timestamp == dt,
            )
        )
        if exists.scalar_one_or_none():
            continue

        session.add(
            SpotPrice(
                symbol=symbol,
                timestamp=dt,
                open=float(k[1]),
                high=float(k[2]),
                low=float(k[3]),
                close=float(k[4]),
                volume=float(k[5]),
            )
        )
        count += 1
    return count


async def poll_binance() -> int:
    total = 0
    async with httpx.AsyncClient() as client:
        for symbol in BINANCE_SYMBOLS:
            try:
                klines = await _fetch_binance_klines(client, symbol)
            except httpx.HTTPStatusError as exc:
                logger.warning("Binance %s: HTTP %s", symbol, exc.response.status_code)
                continue
            except httpx.RequestError as exc:
                logger.warning("Binance %s request error: %s", symbol, exc)
                continue

            async with async_session() as session:
                inserted = await _store_klines(session, symbol, klines)
                await session.commit()
                total += inserted

            logger.debug("Binance %s: %d new candles", symbol, inserted)

    return total


# ── yfinance (sync, run in executor) ─────────────────────


def _poll_yfinance_sync() -> int:
    """Sync function — called via asyncio.to_thread from the scheduler."""
    import yfinance as yf
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.db.database import sync_connect_args, sync_database_url

    engine = create_engine(
        sync_database_url, pool_pre_ping=True, connect_args=sync_connect_args
    )
    total = 0

    for ticker_symbol in YFINANCE_TICKERS:
        try:
            ticker = yf.Ticker(ticker_symbol)
            df = ticker.history(period="5d", interval="1h")
        except Exception as exc:
            logger.warning("yfinance %s error: %s", ticker_symbol, exc)
            continue

        if df.empty:
            continue

        with Session(engine) as session:
            for ts, row in df.iterrows():
                dt = ts.to_pydatetime()
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)

                exists = (
                    session.query(SpotPrice.id)
                    .filter(
                        SpotPrice.symbol == ticker_symbol,
                        SpotPrice.timestamp == dt,
                    )
                    .first()
                )
                if exists:
                    continue

                session.add(
                    SpotPrice(
                        symbol=ticker_symbol,
                        timestamp=dt,
                        open=float(row["Open"]),
                        high=float(row["High"]),
                        low=float(row["Low"]),
                        close=float(row["Close"]),
                        volume=float(row["Volume"]),
                    )
                )
                total += 1
            session.commit()

        logger.debug("yfinance %s: %d candles ingested", ticker_symbol, total)

    engine.dispose()
    return total


async def poll_yfinance() -> int:
    import asyncio
    return await asyncio.to_thread(_poll_yfinance_sync)


# ── Combined ─────────────────────────────────────────────


async def poll_spot() -> dict[str, int]:
    binance_count = await poll_binance()
    yfinance_count = await poll_yfinance()
    stats = {"binance": binance_count, "yfinance": yfinance_count}
    logger.info("Spot poll complete: %s", stats)
    return stats
