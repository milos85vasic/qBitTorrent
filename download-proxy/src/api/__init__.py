"""
FastAPI application and router setup for the merge service.
"""

import os
import logging
import sys
from contextlib import asynccontextmanager

sys.path.insert(0, "/config/download-proxy/src")

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

orchestrator_instance = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator_instance

    logger.info("Starting Merge Service API...")

    from merge_service.search import SearchOrchestrator
    from merge_service.validator import TrackerValidator

    app.state.search_orchestrator = SearchOrchestrator()
    app.state.validator = TrackerValidator()
    orchestrator_instance = app.state.search_orchestrator

    logger.info("Merge Service API started")

    yield

    logger.info("Shutting down Merge Service API...")
    logger.info("Merge Service API stopped")


app = FastAPI(
    title="qBittorrent Merge Search Service",
    description="Search and merge results across multiple torrent trackers",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500, content={"error": "Internal server error", "detail": str(exc)}
    )


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "merge-search", "version": "1.0.0"}


@app.get("/")
async def root():
    return {
        "service": "qBittorrent Merge Search Service",
        "version": "1.0.0",
        "endpoints": {
            "search": "/api/v1/search",
            "search_stream": "/api/v1/search/stream/{search_id}",
            "downloads": "/api/v1/downloads/active",
            "hooks": "/api/v1/hooks",
            "health": "/health",
        },
    }


from .routes import router as api_router
from .hooks import router as hooks_router

app.include_router(api_router, prefix="/api/v1")
app.include_router(hooks_router, prefix="/api/v1")
