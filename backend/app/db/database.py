from __future__ import annotations

import re
import ssl

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

_raw_url: str = settings.database_url

_needs_ssl = "neon.tech" in _raw_url or "sslmode=require" in _raw_url.lower()

def _to_async(url: str) -> str:
    url = re.sub(r"^postgres(ql)?://", "postgresql+asyncpg://", url)
    if "+asyncpg" in url:
        url = re.sub(r"[?&]channel_binding=[^&]*", "", url)
    return url

def _to_sync(url: str) -> str:
    return re.sub(r"^postgres(ql)?(\+\w+)?://", "postgresql://", url)

_async_url = _to_async(_raw_url)
sync_database_url = _to_sync(_raw_url)

connect_args: dict = {}
sync_connect_args: dict = {}

if _needs_ssl:
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    connect_args["ssl"] = ssl_ctx
    sync_connect_args["sslmode"] = "require"

engine = create_async_engine(
    _async_url,
    echo=False,
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,
    connect_args=connect_args,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncSession:  # type: ignore[misc]
    async with async_session() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
