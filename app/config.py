"""
CL-BEDS Configuration Module
Loads all environment variables and exposes typed settings.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "CL-BEDS"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # ── Supabase ─────────────────────────────────────────────────────────────
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    DATABASE_URL: str  # postgresql+asyncpg://user:pass@host:port/db

    # ── JWT ──────────────────────────────────────────────────────────────────
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── LLM ──────────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "gpt-4o-mini"

    # ── CORS ─────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",
        "https://cl-beds.vercel.app",
    ]

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_WINDOW: int = 60

    # ── ML ────────────────────────────────────────────────────────────────────
    MODEL_CACHE_DIR: str = "./ml_cache"
    ROBERTA_MODEL_NAME: str = "j-hartmann/emotion-english-distilroberta-base"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
