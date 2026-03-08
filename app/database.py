"""
CL-BEDS Database — Async SQLAlchemy setup for Supabase (psycopg3)
"""

import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)

_engine = None
_SessionLocal = None


def _get_engine():
    global _engine, _SessionLocal

    if _engine is not None:
        return _engine, _SessionLocal

    from app.config import settings

    url = settings.DATABASE_URL

    # Fix scheme automatically
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    try:
        host_part = url.split("@")[-1]
        logger.info(">>> DB connecting to: %s", host_part)
    except Exception:
        pass

    _engine = create_async_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=settings.DEBUG,
    )

    _SessionLocal = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    return _engine, _SessionLocal


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------
# FastAPI Dependency
# ---------------------------------------------------

async def get_db():
    _, SessionLocal = _get_engine()

    async with SessionLocal() as db:
        try:
            yield db
            await db.commit()
        except Exception:
            await db.rollback()
            raise


# ---------------------------------------------------
# Startup DB check
# ---------------------------------------------------

async def init_db():
    engine, _ = _get_engine()

    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT 1"))
        logger.info(">>> DB ping result: %s", result.scalar())

    logger.info("✅ Database connection OK")
