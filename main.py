"""
main.py — FastAPI application entry point.

Mounts all route modules and handles startup/shutdown lifecycle events.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes import sites, scoring, comparison, hotspots
from core.config import get_settings
from core.database import dispose_engine, get_engine
from core.logger import setup_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    settings = get_settings()
    setup_logging(log_level=settings.log_level)
    logger.info(
        "Starting GeoSpatial Analyzer [env=%s, llm=%s/%s]",
        settings.app_env,
        settings.llm_provider,
        settings.llm_model,
    )

    # Eagerly create the DB engine to validate connectivity
    get_engine()
    logger.info("Database engine initialised")

    yield

    # Shutdown
    await dispose_engine()
    logger.info("Database engine disposed — shutting down")


app = FastAPI(
    title="GeoSpatial Site Readiness Analyzer",
    description=(
        "AI-powered location intelligence API for evaluating and scoring "
        "geographic sites across business use cases."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# ── Mount route modules ──────────────────────────────────────────────────
app.include_router(sites.router)
app.include_router(scoring.router)
app.include_router(comparison.router)
app.include_router(hotspots.router)


@app.get("/", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "GeoSpatial Site Readiness Analyzer",
        "version": "0.1.0",
    }
