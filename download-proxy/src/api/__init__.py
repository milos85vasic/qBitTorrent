"""
FastAPI application and router setup for the merge service.
"""

import os
import logging
import sys
from contextlib import asynccontextmanager

_src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

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
    from merge_service.enricher import MetadataEnricher
    from merge_service.scheduler import Scheduler

    app.state.search_orchestrator = SearchOrchestrator()
    app.state.validator = TrackerValidator()
    app.state.enricher = MetadataEnricher()
    orchestrator_instance = app.state.search_orchestrator

    app.state.scheduler = Scheduler()
    await app.state.scheduler.load()
    app.state.scheduler.set_search_callback(lambda q, c: app.state.search_orchestrator.search(query=q, category=c))
    await app.state.scheduler.start()

    logger.info("Merge Service API started")

    yield

    await app.state.scheduler.stop()
    if hasattr(app.state, "validator") and app.state.validator:
        await app.state.validator.close()
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
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(exc)})


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "merge-search", "version": "1.0.0"}


@app.get("/api/v1/config")
async def get_config():
    from config import get_config as load_config

    cfg = load_config()
    return {
        "qbittorrent_url": f"http://{cfg.qbittorrent_host}:{cfg.qbittorrent_port}",
        "qbittorrent_port": cfg.qbittorrent_port,
        "qbittorrent_host": cfg.qbittorrent_host,
    }


@app.get("/")
@app.get("/dashboard")
async def dashboard():
    dashboard_path = os.path.join(os.path.dirname(__file__), "..", "ui", "templates", "dashboard.html")
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
    orch = app.state.search_orchestrator if hasattr(app.state, "search_orchestrator") else None
    active = 0
    completed = 0
    aborted = 0
    trackers = []
    if orch is not None:
        for sid, meta in orch._active_searches.items():
            if meta.status == "completed":
                completed += 1
            elif meta.status == "aborted":
                aborted += 1
            elif meta.status in ("pending", "running"):
                active += 1
        enabled_trackers = orch._get_enabled_trackers()
        trackers = [{"name": t.name, "url": t.url, "enabled": t.enabled} for t in enabled_trackers]
    return {
        "active_searches": active,
        "completed_searches": completed,
        "aborted_searches": aborted,
        "total_searches": active + completed + aborted,
        "trackers": trackers,
        "trackers_count": len(trackers),
    }


from .routes import router as api_router
from .hooks import router as hooks_router
from .auth import router as auth_router
from .scheduler import router as scheduler_router

app.include_router(api_router, prefix="/api/v1")
app.include_router(hooks_router, prefix="/api/v1/hooks")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(scheduler_router, prefix="/api/v1/schedules")
