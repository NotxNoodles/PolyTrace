"""Master API router — aggregates all sub-routers under /api."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.smart_money import router as smart_money_router
from app.api.wallet import router as wallet_router
from app.api.oracle import router as oracle_router

api_router = APIRouter(prefix="/api")
api_router.include_router(smart_money_router)
api_router.include_router(wallet_router)
api_router.include_router(oracle_router)
