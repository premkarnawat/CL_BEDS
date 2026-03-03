"""
CL-BEDS: Cognitive Load & Burnout Early Detection System
Main FastAPI Application Entry Point
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.config import settings
from app.database import init_db
from app.models.burnout_model import BurnoutModel
from app.models.roberta_model import RoBERTaEmotionModel
from app.api.routes_auth      import router as auth_router
from app.api.routes_stream    import router as stream_router
from app.api.routes_dashboard import router as dashboard_router
from app.api.routes_chat      import router as chat_router
from app.api.routes_journal   import router as journal_router
from app.api.routes_profile   import router as profile_router
from app.api.routes_admin     import router as admin_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀  CL-BEDS backend starting …")
    await init_db()
    logger.info("✅  Database pool ready")

    bm = BurnoutModel(); bm.load()
    app.state.burnout_model = bm
    logger.info("✅  Burnout fusion model loaded")

    rm = RoBERTaEmotionModel(); rm.load()
    app.state.roberta_model = rm
    logger.info("✅  RoBERTa emotion model loaded")

    yield
    logger.info("🛑  CL-BEDS backend shutting down …")


app = FastAPI(
    title="CL-BEDS API",
    description="Cognitive Load & Burnout Early Detection System",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if not settings.DEBUG:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

app.include_router(auth_router,      prefix="/auth",      tags=["Authentication"])
app.include_router(stream_router,    prefix="/ws",        tags=["WebSocket Stream"])
app.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(chat_router,      prefix="/chat",      tags=["AI Coach Chatbot"])
app.include_router(journal_router,   prefix="/journal",   tags=["Journal"])
app.include_router(profile_router,   prefix="/profile",   tags=["User Profile"])
app.include_router(admin_router,     prefix="/admin",     tags=["Admin"])


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "service": "cl-beds-api", "version": "1.0.0"}
