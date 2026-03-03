from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


# ── Enums ────────────────────────────────────────────────


class WalletClassification(str, enum.Enum):
    SNIPER = "sniper"
    SPECIALIST = "specialist"
    ONE_HIT = "one_hit"
    UNKNOWN = "unknown"


class AlertType(str, enum.Enum):
    SNIPER = "sniper"
    SPECIALIST = "specialist"
    ONE_HIT = "one_hit"


class SignalType(str, enum.Enum):
    BULLISH_LEAD = "bullish_lead"
    BEARISH_LEAD = "bearish_lead"
    NOISE = "noise"


class TradeSide(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


# ── Markets ──────────────────────────────────────────────


class Market(Base):
    __tablename__ = "markets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    condition_id: Mapped[str] = mapped_column(String(66), unique=True, index=True)
    question_id: Mapped[str | None] = mapped_column(String(66))
    slug: Mapped[str | None] = mapped_column(String(512))
    question: Mapped[str | None] = mapped_column(Text)
    outcomes: Mapped[dict | None] = mapped_column(JSONB)
    tags: Mapped[dict | None] = mapped_column(JSONB)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    volume: Mapped[float | None] = mapped_column(Float)
    liquidity: Mapped[float | None] = mapped_column(Float)
    clob_token_ids: Mapped[dict | None] = mapped_column(JSONB)
    event_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── Market Prices (time-series) ──────────────────────────


class MarketPrice(Base):
    __tablename__ = "market_prices"
    __table_args__ = (
        Index("ix_market_prices_cond_ts", "condition_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    condition_id: Mapped[str] = mapped_column(String(66), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    yes_price: Mapped[float] = mapped_column(Float)
    no_price: Mapped[float] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)


# ── Spot Prices (time-series) ────────────────────────────


class SpotPrice(Base):
    __tablename__ = "spot_prices"
    __table_args__ = (
        Index("ix_spot_prices_sym_ts", "symbol", "timestamp"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)


# ── Wallets ──────────────────────────────────────────────


class Wallet(Base):
    __tablename__ = "wallets"

    address: Mapped[str] = mapped_column(String(42), primary_key=True)
    label: Mapped[str | None] = mapped_column(String(128))
    classification: Mapped[WalletClassification] = mapped_column(
        Enum(WalletClassification), default=WalletClassification.UNKNOWN
    )
    total_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    tags_specialty: Mapped[dict | None] = mapped_column(JSONB)
    first_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)


# ── Wallet Trades ────────────────────────────────────────


class WalletTrade(Base):
    __tablename__ = "wallet_trades"
    __table_args__ = (
        Index("ix_wallet_trades_addr_ts", "wallet_address", "timestamp"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    wallet_address: Mapped[str] = mapped_column(String(42), index=True)
    condition_id: Mapped[str] = mapped_column(String(66), index=True)
    side: Mapped[TradeSide] = mapped_column(Enum(TradeSide))
    price: Mapped[float] = mapped_column(Float)
    size: Mapped[float] = mapped_column(Float)
    usdc_size: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    tx_hash: Mapped[str | None] = mapped_column(String(66))


# ── Wallet Positions ─────────────────────────────────────


class WalletPosition(Base):
    __tablename__ = "wallet_positions"
    __table_args__ = (
        Index("ix_wallet_pos_addr_cond", "wallet_address", "condition_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    wallet_address: Mapped[str] = mapped_column(String(42), index=True)
    condition_id: Mapped[str] = mapped_column(String(66), index=True)
    size: Mapped[float] = mapped_column(Float)
    avg_price: Mapped[float] = mapped_column(Float)
    current_value: Mapped[float] = mapped_column(Float, default=0.0)
    cash_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    percent_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    outcome: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ── On-Chain Transfers ───────────────────────────────────


class OnchainTransfer(Base):
    __tablename__ = "onchain_transfers"
    __table_args__ = (
        Index("ix_transfers_from", "from_address"),
        Index("ix_transfers_to", "to_address"),
        Index("ix_transfers_block", "block_number"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tx_hash: Mapped[str] = mapped_column(String(66), index=True)
    from_address: Mapped[str] = mapped_column(String(42))
    to_address: Mapped[str] = mapped_column(String(42))
    token_id: Mapped[str] = mapped_column(String(78))
    value: Mapped[str] = mapped_column(String(78))
    block_number: Mapped[int] = mapped_column(BigInteger)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# ── Oracle Signals ───────────────────────────────────────


class OracleSignal(Base):
    __tablename__ = "oracle_signals"
    __table_args__ = (
        Index("ix_oracle_sig_cond_ts", "condition_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    condition_id: Mapped[str] = mapped_column(String(66), index=True)
    spot_symbol: Mapped[str] = mapped_column(String(20))
    poly_delta_p: Mapped[float] = mapped_column(Float)
    spot_delta_s: Mapped[float] = mapped_column(Float)
    dac_score: Mapped[float] = mapped_column(Float)
    ttr_hours: Mapped[float] = mapped_column(Float)
    volume_surge_ratio: Mapped[float] = mapped_column(Float)
    signal_type: Mapped[SignalType] = mapped_column(Enum(SignalType))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


# ── Smart Money Alerts ───────────────────────────────────


class SmartMoneyAlert(Base):
    __tablename__ = "smart_money_alerts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    wallet_address: Mapped[str] = mapped_column(String(42), index=True)
    condition_id: Mapped[str] = mapped_column(String(66), index=True)
    alert_type: Mapped[AlertType] = mapped_column(Enum(AlertType))
    confidence: Mapped[float] = mapped_column(Float)
    usdc_volume: Mapped[float] = mapped_column(Float)
    description: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
