"""
Store Intelligence API — FastAPI Application Entrypoint.

A real-time analytics API for offline retail store intelligence.
Built for the Purplle Tech Challenge 2026.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.staticfiles import StaticFiles

from app.database import db
from app.middleware import RequestLoggingMiddleware
from app.pos_loader import load_pos_data

# Import route modules
from app.ingestion import router as ingestion_router
from app.metrics import router as metrics_router
from app.funnel import router as funnel_router
from app.heatmap import router as heatmap_router
from app.anomalies import router as anomalies_router
from app.health import router as health_router
from app.websocket import router as websocket_router
from app.demo import router as demo_router

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Application Lifespan (startup / shutdown)
# ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle — DB connection pool + POS data loading."""
    # Startup
    logger.info("🚀 Starting Store Intelligence API...")

    try:
        await db.connect()
        logger.info("✅ Database connected")

        # Load POS transaction data
        pos_count = await load_pos_data()
        logger.info(f"✅ POS data loaded ({pos_count} rows)")

    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        # Continue even if DB fails — health endpoint will report unhealthy

    yield

    # Shutdown
    logger.info("🛑 Shutting down Store Intelligence API...")
    await db.disconnect()
    logger.info("✅ Cleanup complete")


# ─────────────────────────────────────────────
# FastAPI Application
# ─────────────────────────────────────────────

app = FastAPI(
    title="Store Intelligence API",
    description=(
        "Real-time analytics API for offline retail store intelligence. "
        "Ingests detection events from CCTV footage, computes live metrics, "
        "tracks conversion funnels, generates zone heatmaps, and detects anomalies."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ─────────────────────────────────────────────
# Middleware
# ─────────────────────────────────────────────

# CORS — allow dashboard and external access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Structured request logging
app.add_middleware(RequestLoggingMiddleware)


# ─────────────────────────────────────────────
# Error Handlers — Graceful Degradation
# ─────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler — ensures no raw stack traces in responses.
    Returns structured error JSON.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred. Please try again later.",
            "trace_id": getattr(request.state, "trace_id", None),
        },
    )


# ─────────────────────────────────────────────
# Route Registration
# ─────────────────────────────────────────────

app.include_router(ingestion_router)
app.include_router(metrics_router)
app.include_router(funnel_router)
app.include_router(heatmap_router)
app.include_router(anomalies_router)
app.include_router(health_router)
app.include_router(websocket_router)
app.include_router(demo_router)


# ─────────────────────────────────────────────
# Root Endpoint
# ─────────────────────────────────────────────

@app.get("/", tags=["Root"])
async def root():
    """API root — basic info and links."""
    return {
        "service": "Store Intelligence API",
        "version": "1.0.0",
        "store_id": "ST1008",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "ingest": "POST /events/ingest",
            "metrics": "GET /stores/{store_id}/metrics",
            "funnel": "GET /stores/{store_id}/funnel",
            "heatmap": "GET /stores/{store_id}/heatmap",
            "anomalies": "GET /stores/{store_id}/anomalies",
            "websocket": "ws://host/ws/live/{store_id}",
        },
    }
