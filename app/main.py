"""
CL-BEDS: Cognitive Load & Burnout Early Detection System
Main FastAPI Application Entry Point
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

# -------------------------------------------------------------------
# Debug database URL at startup
# -------------------------------------------------------------------
print("==============================")
print("RAW DATABASE_URL:", os.environ.get("DATABASE_URL", "NOT SET AT ALL"))
print("==============================")

# -------------------------------------------------------------------
# Logging
# -------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Lifespan (startup + shutdown)
# -------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("CL-BEDS backend starting")

    await init_db()
    logger.info("Database pool ready")

    bm = BurnoutModel()
    bm.load()
    app.state.burnout_model = bm
    logger.info("Burnout fusion model loaded")

    rm = RoBERTaEmotionModel()
    rm.load()
    app.state.roberta_model = rm
    logger.info("RoBERTa emotion model ready")

    yield

    logger.info("CL-BEDS backend shutting down")


# -------------------------------------------------------------------
# FastAPI Application
# -------------------------------------------------------------------
app = FastAPI(
    title="CL-BEDS API",
    description="Cognitive Load & Burnout Early Detection System",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# -------------------------------------------------------------------
# CORS — must be FIRST middleware
# NOTE: TrustedHostMiddleware removed — it blocks OPTIONS preflight
# requests with 400, breaking login/register from the frontend.
# -------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://cl-beds.vercel.app",
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------
# Routers
# -------------------------------------------------------------------
app.include_router(auth_router,      prefix="/auth",      tags=["Authentication"])
app.include_router(stream_router,    prefix="/ws",        tags=["WebSocket Stream"])
app.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(chat_router,      prefix="/chat",      tags=["AI Coach Chatbot"])
app.include_router(journal_router,   prefix="/journal",   tags=["Journal"])
app.include_router(profile_router,   prefix="/profile",   tags=["User Profile"])
app.include_router(admin_router,     prefix="/admin",     tags=["Admin"])


# -------------------------------------------------------------------
# Root
# -------------------------------------------------------------------
@app.get("/", tags=["System"])
async def root():
    return {
        "service": "CL-BEDS API",
        "status": "running",
        "version": "1.0.0",
        "docs": "/docs",
    }


# -------------------------------------------------------------------
# Health (used by Render + monitoring)
# -------------------------------------------------------------------
@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "ok",
        "service": "cl-beds-api",
        "version": "1.0.0",
    }
