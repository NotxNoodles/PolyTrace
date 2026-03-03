"""Listen to Polygon chain events for Polymarket CTF token transfers.

Tracks TransferSingle and TransferBatch events from the Conditional Tokens
contract (0x4D97DCd97eC945f40cF65F87097ACe5EA0476045) on Polygon (chain 137).

Requires POLYGON_RPC_URL in .env.  Uses web3.py with HTTPProvider for
block-range polling (websocket subscription can be swapped in via
POLYGON_WS_URL when available).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import async_session
from app.db.models import OnchainTransfer

logger = logging.getLogger(__name__)

CTF_ADDRESS = settings.conditional_tokens

TRANSFER_SINGLE_TOPIC = (
    "0xc3d58168c5ae7397731d063d5bbf3d657854427343f4c083240f7aacaa2d0f62"
)
TRANSFER_BATCH_TOPIC = (
    "0x4a39dc06d4c0dbc64b70af90fd698a233a518aa5d07e595d983b8c0526c8f7fb"
)

BLOCK_RANGE = 2000  # ~1 hour of Polygon blocks (2s block time)


def _get_web3():
    from web3 import Web3

    if not settings.polygon_rpc_url:
        raise RuntimeError("POLYGON_RPC_URL not configured")
    return Web3(Web3.HTTPProvider(settings.polygon_rpc_url))


async def _get_last_block(session: AsyncSession) -> int | None:
    result = await session.execute(
        select(func.max(OnchainTransfer.block_number))
    )
    return result.scalar_one_or_none()


def _parse_transfer_single_log(log: dict[str, Any]) -> dict[str, Any] | None:
    """Decode a TransferSingle log entry."""
    try:
        topics = log.get("topics", [])
        data = log.get("data", "0x")

        if len(topics) < 4:
            return None

        operator = "0x" + topics[1].hex()[-40:]
        from_addr = "0x" + topics[2].hex()[-40:]
        to_addr = "0x" + topics[3].hex()[-40:]

        # data contains: id (uint256) + value (uint256)
        data_hex = data.hex() if isinstance(data, bytes) else data.replace("0x", "")
        if len(data_hex) < 128:
            return None

        token_id = str(int(data_hex[:64], 16))
        value = str(int(data_hex[64:128], 16))

        return {
            "tx_hash": log["transactionHash"].hex()
            if isinstance(log["transactionHash"], bytes)
            else log["transactionHash"],
            "from_address": from_addr.lower(),
            "to_address": to_addr.lower(),
            "token_id": token_id,
            "value": value,
            "block_number": log["blockNumber"],
        }
    except Exception as exc:
        logger.debug("Failed to parse TransferSingle log: %s", exc)
        return None


def _parse_transfer_batch_log(log: dict[str, Any]) -> list[dict[str, Any]]:
    """Decode a TransferBatch log into multiple transfer records."""
    results = []
    try:
        topics = log.get("topics", [])
        data = log.get("data", "0x")

        if len(topics) < 4:
            return results

        from_addr = "0x" + topics[2].hex()[-40:]
        to_addr = "0x" + topics[3].hex()[-40:]

        data_hex = data.hex() if isinstance(data, bytes) else data.replace("0x", "")

        # ABI-encoded: offset_ids, offset_values, len_ids, id[], len_values, value[]
        # Simplified: extract as many id/value pairs as possible
        tx_hash = (
            log["transactionHash"].hex()
            if isinstance(log["transactionHash"], bytes)
            else log["transactionHash"]
        )

        # Batch decoding is complex — store the raw batch as a single record
        # for now and let the heuristics engine expand later if needed.
        results.append(
            {
                "tx_hash": tx_hash,
                "from_address": from_addr.lower(),
                "to_address": to_addr.lower(),
                "token_id": "batch",
                "value": str(len(data_hex) // 64),
                "block_number": log["blockNumber"],
            }
        )
    except Exception as exc:
        logger.debug("Failed to parse TransferBatch log: %s", exc)
    return results


def _poll_blocks_sync(from_block: int, to_block: int) -> list[dict[str, Any]]:
    """Sync function to query Polygon RPC for CTF transfer logs."""
    w3 = _get_web3()

    log_filter = {
        "fromBlock": from_block,
        "toBlock": to_block,
        "address": w3.to_checksum_address(CTF_ADDRESS),
        "topics": [[TRANSFER_SINGLE_TOPIC, TRANSFER_BATCH_TOPIC]],
    }

    raw_logs = w3.eth.get_logs(log_filter)
    transfers: list[dict[str, Any]] = []

    for log in raw_logs:
        topic0 = log["topics"][0].hex() if isinstance(log["topics"][0], bytes) else log["topics"][0]

        if topic0 == TRANSFER_SINGLE_TOPIC:
            parsed = _parse_transfer_single_log(log)
            if parsed:
                transfers.append(parsed)
        elif topic0 == TRANSFER_BATCH_TOPIC:
            transfers.extend(_parse_transfer_batch_log(log))

    return transfers


async def poll_chain() -> int:
    """Poll recent Polygon blocks for CTF transfers.  Returns rows inserted."""
    if not settings.polygon_rpc_url:
        logger.debug("Chain listener skipped: no POLYGON_RPC_URL configured")
        return 0

    import asyncio

    w3 = await asyncio.to_thread(_get_web3)
    current_block = await asyncio.to_thread(lambda: w3.eth.block_number)

    async with async_session() as session:
        last_stored = await _get_last_block(session)

    from_block = (last_stored + 1) if last_stored else (current_block - BLOCK_RANGE)
    to_block = min(from_block + BLOCK_RANGE, current_block)

    if from_block >= to_block:
        return 0

    try:
        transfers = await asyncio.to_thread(_poll_blocks_sync, from_block, to_block)
    except Exception as exc:
        logger.error("Chain poll error blocks %d-%d: %s", from_block, to_block, exc)
        return 0

    total = 0
    async with async_session() as session:
        for t in transfers:
            # Get block timestamp
            try:
                block = await asyncio.to_thread(
                    lambda bn=t["block_number"]: w3.eth.get_block(bn)
                )
                ts = datetime.fromtimestamp(block["timestamp"], tz=timezone.utc)
            except Exception:
                ts = datetime.now(timezone.utc)

            exists = await session.execute(
                select(OnchainTransfer.id).where(
                    OnchainTransfer.tx_hash == t["tx_hash"],
                    OnchainTransfer.from_address == t["from_address"],
                    OnchainTransfer.token_id == t["token_id"],
                )
            )
            if exists.scalar_one_or_none():
                continue

            session.add(
                OnchainTransfer(
                    tx_hash=t["tx_hash"],
                    from_address=t["from_address"],
                    to_address=t["to_address"],
                    token_id=t["token_id"],
                    value=t["value"],
                    block_number=t["block_number"],
                    timestamp=ts,
                )
            )
            total += 1

        await session.commit()

    logger.info("Chain poll blocks %d-%d: %d transfers stored", from_block, to_block, total)
    return total
