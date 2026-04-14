"""
FastAPI application and router setup for the merge service.
"""

import os
import logging
import sys
from contextlib import asynccontextmanager

sys.path.insert(0, "/config/download-proxy/src")

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
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
@app.get("/dashboard")
async def dashboard():
    dashboard_path = os.path.join(
        os.path.dirname(__file__), "..", "ui", "templates", "dashboard.html"
    )
    dashboard_path = os.path.normpath(dashboard_path)
    if os.path.isfile(dashboard_path):
        return FileResponse(dashboard_path)
    return {
        "message": "Merge Search API",
        "version": "1.0.0",
        "dashboard": "not found",
    }


@app.get("/api/v1/stats")
async def stats():
    orch = (
        app.state.search_orchestrator
        if hasattr(app.state, "search_orchestrator")
        else None
    )
    active = 0
    completed = 0
    trackers = []
    if orch is not None:
        for sid, meta in orch._active_searches.items():
            if meta.status == "completed":
                completed += 1
            elif meta.status in ("pending", "running"):
                active += 1
        enabled_trackers = orch._get_enabled_trackers()
        trackers = [
            {"name": t.name, "url": t.url, "enabled": t.enabled}
            for t in enabled_trackers
        ]
    return {
        "active_searches": active,
        "completed_searches": completed,
        "total_searches": active + completed,
        "trackers": trackers,
        "trackers_count": len(trackers),
    }


from .routes import router as api_router
from .hooks import router as hooks_router

app.include_router(api_router, prefix="/api/v1")
app.include_router(hooks_router, prefix="/api/v1")
