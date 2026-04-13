"""
FastAPI application and router setup for the merge service.

This module sets up the main FastAPI app with all routes for:
- Search endpoints (POST /search, GET /search/stream/{searchId})
- Download endpoints (GET /downloads/active)
- Hooks endpoints (GET/POST /hooks)
- Health endpoint (GET /health)
"""

import os
import logging
import sys
from contextlib import asynccontextmanager
from typing import Optional

sys.path.insert(0, "/config/download-proxy/src")

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# Application state
app_state = {
    "searches": {},  # search_id -> SearchMetadata
    "downloads": {},  # download_id -> download info
    "hooks": [],  # registered hooks
    "scheduler": None,  # scheduler instance
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting Merge Service API...")

    # Initialize services
    from merge_service.search import SearchOrchestrator
    from merge_service.validator import TrackerValidator

    app.state.search_orchestrator = SearchOrchestrator()
    app.state.validator = TrackerValidator()

    logger.info("Merge Service API started")

    yield

    # Shutdown
    logger.info("Shutting down Merge Service API...")
    if hasattr(app.state, "validator"):
        await app.state.validator.close()
    logger.info("Merge Service API stopped")


# Create FastAPI app
app = FastAPI(
    title="qBittorrent Merge Search Service",
    description="Search and merge results across multiple torrent trackers",
    version="1.0.0",
    lifespan=lifespan,
)


# Error handling
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500, content={"error": "Internal server error", "detail": str(exc)}
    )


# Health endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "merge-search", "version": "1.0.0"}


# Placeholder for routes - will be populated in Phase 3
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "qBittorrent Merge Search Service",
        "version": "1.0.0",
        "endpoints": {
            "search": "/search",
            "search_stream": "/search/stream/{search_id}",
            "downloads": "/downloads/active",
            "hooks": "/hooks",
            "health": "/health",
        },
    }


# Include router
from .routes import router as api_router
from .hooks import router as hooks_router

app.include_router(api_router, prefix="/api/v1")
app.include_router(hooks_router, prefix="/api/v1")
