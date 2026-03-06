"""
CL-BEDS Database — lazy asyncpg engine. No psycopg2.
"""
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
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

    # ── Fix URL scheme for asyncpg ─────────────────────────────────────
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # ── Debug log: shows host without exposing password ────────────────
    try:
        host_part = url.split("@")[-1]
        logger.info(">>> DB connecting to: %s", host_part)
    except Exception:
        pass

    # ── Create engine (SSL required for Supabase) ──────────────────────
    # Do NOT set pool_size / max_overflow — conflicts with Supabase pooler
    _engine = create_async_engine(
        url,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={"ssl": "require"},
    )

    _SessionLocal = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    return _engine, _SessionLocal


class Base(DeclarativeBase):
    pass


async def get_db():
    _, SessionLocal = _get_engine()
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    engine, _ = _get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        logger.info(">>> DB ping result: %s", result.scalar())
    logger.info("✅ Database connection OK")
