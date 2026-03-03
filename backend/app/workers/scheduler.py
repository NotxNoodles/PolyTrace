"""APScheduler background workers for periodic data ingestion and analysis.

Each job is wrapped with error handling so a single failure doesn't crash
the scheduler.  All jobs fire IMMEDIATELY on startup, then repeat at their
configured intervals.
"""

from __future__ import annotations

import asyncio
import logging
import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║               PolyTrace — Job Scheduler                      ║
╚══════════════════════════════════════════════════════════════╝"""


async def _safe_run(name: str, coro):
    """Run an async job with error isolation and timing."""
    start = time.monotonic()
    logger.info("┌── [%s] STARTING ──────────────────────────", name)
    try:
        result = await coro
        elapsed = time.monotonic() - start
        logger.info(
            "└── [%s] COMPLETED in %.1fs → %s",
            name,
            elapsed,
            result,
        )
    except Exception as exc:
        elapsed = time.monotonic() - start
        logger.error(
            "└── [%s] FAILED after %.1fs → %s: %s",
            name,
            elapsed,
            type(exc).__name__,
            exc,
        )


def _add_job(name: str, func, seconds: int):
    async def wrapper():
        await _safe_run(name, func())

    scheduler.add_job(
        wrapper,
        trigger=IntervalTrigger(seconds=seconds),
        id=name,
        name=name,
        replace_existing=True,
    )


async def _run_initial_jobs():
    """Fire all ingestion jobs immediately on startup in the right order.

    Order matters: Gamma must run first to populate markets, then the
    downstream pollers can find markets to query.
    """
    from app.ingestion.gamma_poller import poll_gamma
    from app.ingestion.clob_poller import poll_clob_prices
    from app.ingestion.data_api_poller import poll_data_api
    from app.ingestion.spot_poller import poll_spot
    from app.ingestion.chain_listener import poll_chain
    from app.engines.heuristics import run_heuristics
    from app.engines.oracle import run_oracle

    logger.info("🚀 Running initial data ingestion (all jobs fire NOW)...")

    # Phase 1: Gamma + Spot (independent, run in parallel)
    logger.info("━━━ Phase 1: Market discovery + Spot prices ━━━")
    await asyncio.gather(
        _safe_run("gamma_poller", poll_gamma()),
        _safe_run("spot_poller", poll_spot()),
    )

    # Phase 2: CLOB + Data API + Chain (depend on markets existing)
    logger.info("━━━ Phase 2: Price history + Trades + On-chain ━━━")
    await asyncio.gather(
        _safe_run("clob_poller", poll_clob_prices()),
        _safe_run("data_api_poller", poll_data_api()),
        _safe_run("chain_listener", poll_chain()),
    )

    # Phase 3: Analysis engines (depend on data from phases 1-2)
    logger.info("━━━ Phase 3: Analysis engines ━━━")
    await asyncio.gather(
        _safe_run("heuristics_engine", run_heuristics()),
        _safe_run("oracle_engine", run_oracle()),
    )

    logger.info("✅ Initial ingestion complete — switching to interval polling")


def setup_scheduler():
    """Register all periodic jobs and schedule the initial burst."""
    from app.ingestion.gamma_poller import poll_gamma
    from app.ingestion.clob_poller import poll_clob_prices
    from app.ingestion.data_api_poller import poll_data_api
    from app.ingestion.spot_poller import poll_spot
    from app.ingestion.chain_listener import poll_chain
    from app.engines.heuristics import run_heuristics
    from app.engines.oracle import run_oracle

    logger.info(BANNER)

    _add_job("gamma_poller", poll_gamma, settings.gamma_poll_interval)
    _add_job("clob_poller", poll_clob_prices, settings.clob_poll_interval)
    _add_job("data_api_poller", poll_data_api, settings.data_api_poll_interval)
    _add_job("spot_poller", poll_spot, settings.spot_poll_interval)
    _add_job("chain_listener", poll_chain, settings.gamma_poll_interval)
    _add_job("heuristics_engine", run_heuristics, settings.heuristics_run_interval)
    _add_job("oracle_engine", run_oracle, settings.oracle_run_interval)

    scheduler.start()

    for job in scheduler.get_jobs():
        logger.info(
            "  📋 %-20s  every %ss  next: %s",
            job.name,
            job.trigger.interval.total_seconds(),
            job.next_run_time.strftime("%H:%M:%S") if job.next_run_time else "—",
        )

    # Fire the initial burst as a background task
    asyncio.get_event_loop().create_task(_run_initial_jobs())
