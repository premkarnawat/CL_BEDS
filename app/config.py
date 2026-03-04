"""
CL-BEDS Configuration Module
Loads all environment variables and exposes typed settings.
"""

from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── App ───────────────────────────────────────────────────────────────
    APP_NAME: str = "CL-BEDS"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # ── Supabase / Database ───────────────────────────────────────────────
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    DATABASE_URL: str = ""   # postgresql+asyncpg://user:pass@host:port/db

    # ── JWT / Auth ────────────────────────────────────────────────────────
    # Render generates SECRET_KEY automatically; we alias it as JWT_SECRET
    SECRET_KEY: str = "change-me-in-production"
    JWT_SECRET: str = ""          # falls back to SECRET_KEY if blank
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── LLM ───────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    LLM_PROVIDER: str = "openai"   # openai | anthropic | groq
    LLM_MODEL: str = "gpt-4o-mini"

    # ── CORS / Hosts ──────────────────────────────────────────────────────
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",
        "https://cl-beds.vercel.app",
    ]
    ALLOWED_HOSTS: List[str] = ["*"]   # tighten in production

    # ── Rate Limiting ─────────────────────────────────────────────────────
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_WINDOW: int = 60

    # ── ML ────────────────────────────────────────────────────────────────
    MODEL_CACHE_DIR: str = "./ml_cache"
    ROBERTA_MODEL_NAME: str = "cardiffnlp/twitter-roberta-base-emotion"

    def get_jwt_secret(self) -> str:
        """Return JWT_SECRET if set, otherwise fall back to SECRET_KEY."""
        return self.JWT_SECRET or self.SECRET_KEY

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# Module-level singleton — allows `from app.config import settings`
settings = get_settings()
 
