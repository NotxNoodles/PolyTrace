"""FastAPI application entrypoint.

Lifespan context manager initializes the database and starts the background
scheduler.  CORS is configured for the frontend dev server.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import settings
from app.db.database import init_db
from app.workers.scheduler import setup_scheduler, scheduler

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
# Suppress noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("apscheduler.scheduler").setLevel(logging.WARNING)
logging.getLogger("apscheduler.executors").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("  PolyTrace v0.1.0 — starting up")
    logger.info("  DB: %s", settings.database_url.split("@")[-1] if "@" in settings.database_url else "local")
    logger.info("=" * 60)
    await init_db()
    logger.info("Database tables ready")
    setup_scheduler()
    yield
    scheduler.shutdown(wait=False)
    logger.info("PolyTrace shut down.")


app = FastAPI(
    title="PolyTrace",
    description="Polymarket Insider & Oracle Tracker",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "polytrace"}
