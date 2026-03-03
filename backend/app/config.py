from __future__ import annotations

import json
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database ─────────────────────────────────────────
    database_url: str = (
        "postgresql+asyncpg://polytrace:polytrace@localhost:5432/polytrace"
    )
    database_url_sync: str = (
        "postgresql://polytrace:polytrace@localhost:5432/polytrace"
    )

    # ── Polygon RPC ──────────────────────────────────────
    polygon_rpc_url: str = ""
    polygon_ws_url: str = ""

    # ── Polymarket APIs ──────────────────────────────────
    gamma_api_url: str = "https://gamma-api.polymarket.com"
    data_api_url: str = "https://data-api.polymarket.com"
    clob_api_url: str = "https://clob.polymarket.com"

    # ── Spot Market APIs ─────────────────────────────────
    binance_api_url: str = "https://api.binance.com"

    # ── App Config ───────────────────────────────────────
    cors_origins: List[str] = ["http://localhost:3000"]
    log_level: str = "INFO"

    # ── Polling Intervals (seconds) ──────────────────────
    gamma_poll_interval: int = 300
    clob_poll_interval: int = 60
    data_api_poll_interval: int = 120
    spot_poll_interval: int = 60
    heuristics_run_interval: int = 600
    oracle_run_interval: int = 120

    # ── Polymarket Contract Addresses (Polygon) ──────────
    ctf_exchange: str = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
    neg_risk_ctf_exchange: str = "0xC5d563A36AE78145C45a50134d48A1215220f80a"
    conditional_tokens: str = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
    usdc_e: str = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"


settings = Settings()
