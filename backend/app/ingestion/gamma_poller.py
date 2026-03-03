"""Poll the Polymarket Gamma API for events and markets.

Gamma API is fully public (no auth).  Rate guidance: ~100 req/min.
We paginate through /events and upsert into the `markets` table.
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
from app.db.models import Market

logger = logging.getLogger(__name__)

BASE = settings.gamma_api_url
PAGE_SIZE = 100
MAX_PAGES = 50  # safety cap: 5 000 events per run


async def _fetch_page(
    client: httpx.AsyncClient, offset: int
) -> list[dict[str, Any]]:
    resp = await client.get(
        f"{BASE}/events",
        params={
            "active": "true",
            "closed": "false",
            "limit": PAGE_SIZE,
            "offset": offset,
            "order": "volume",
            "ascending": "false",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _parse_end_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _extract_markets(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten an event into a list of market dicts ready for upsert."""
    markets_raw = event.get("markets") or []
    results: list[dict[str, Any]] = []
    for m in markets_raw:
        clob_ids = {}
        tokens = m.get("clobTokenIds")
        if tokens:
            # tokens is a comma-separated string or a JSON array string
            if isinstance(tokens, str):
                try:
                    import json
                    clob_ids = {"ids": json.loads(tokens)}
                except Exception:
                    clob_ids = {"ids": tokens.split(",")}
            elif isinstance(tokens, list):
                clob_ids = {"ids": tokens}

        outcomes_raw = m.get("outcomes", "[]")
        if isinstance(outcomes_raw, str):
            import json
            try:
                outcomes_parsed = json.loads(outcomes_raw)
            except Exception:
                outcomes_parsed = [outcomes_raw]
        else:
            outcomes_parsed = outcomes_raw

        tags_raw = event.get("tags") or []
        tag_list = [t.get("label") or t.get("slug") for t in tags_raw if isinstance(t, dict)]

        results.append(
            {
                "condition_id": m.get("conditionId", ""),
                "question_id": m.get("questionID"),
                "slug": m.get("slug") or event.get("slug"),
                "question": m.get("question") or event.get("title"),
                "outcomes": outcomes_parsed,
                "tags": tag_list,
                "end_date": _parse_end_date(m.get("endDate") or event.get("endDate")),
                "active": m.get("active", True),
                "volume": _safe_float(m.get("volume")),
                "liquidity": _safe_float(m.get("liquidity")),
                "clob_token_ids": clob_ids,
                "event_id": str(event.get("id", "")),
            }
        )
    return results


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


async def _upsert_market(session: AsyncSession, data: dict[str, Any]) -> None:
    result = await session.execute(
        select(Market).where(Market.condition_id == data["condition_id"])
    )
    existing = result.scalar_one_or_none()
    if existing:
        for key, val in data.items():
            setattr(existing, key, val)
    else:
        session.add(Market(**data))


async def poll_gamma() -> int:
    """Fetch all active events/markets and upsert them.  Returns count."""
    total = 0
    async with httpx.AsyncClient() as client:
        for page in range(MAX_PAGES):
            offset = page * PAGE_SIZE
            try:
                events = await _fetch_page(client, offset)
            except httpx.HTTPStatusError as exc:
                logger.error("Gamma API HTTP %s at offset %d", exc.response.status_code, offset)
                break
            except httpx.RequestError as exc:
                logger.error("Gamma API request error: %s", exc)
                break

            if not events:
                break

            async with async_session() as session:
                for event in events:
                    for market_data in _extract_markets(event):
                        if not market_data["condition_id"]:
                            continue
                        await _upsert_market(session, market_data)
                        total += 1
                await session.commit()

            logger.info("Gamma poll page %d: %d events", page, len(events))

            if len(events) < PAGE_SIZE:
                break

    logger.info("Gamma poll complete: %d markets upserted", total)
    return total
