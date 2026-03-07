"""
CL-BEDS Database — Supabase + SQLAlchemy setup (psycopg3).
"""

import logging
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import create_engine

logger = logging.getLogger(__name__)

_engine = None
_SessionLocal = None


def _get_engine():
    global _engine, _SessionLocal

    if _engine is not None:
        return _engine, _SessionLocal

    from app.config import settings

    url = settings.DATABASE_URL

    # Fix scheme if needed
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    try:
        host_part = url.split("@")[-1]
        logger.info(">>> DB connecting to: %s", host_part)
    except Exception:
        pass

    _engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=settings.DEBUG,
    )

    _SessionLocal = sessionmaker(
        bind=_engine,
        autoflush=False,
        autocommit=False,
    )

    return _engine, _SessionLocal


class Base(DeclarativeBase):
    pass


def get_db():
    _, SessionLocal = _get_engine()
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def init_db():
    engine, _ = _get_engine()

    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        logger.info(">>> DB ping result: %s", result.scalar())

    logger.info("✅ Database connection OK")
