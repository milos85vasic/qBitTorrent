"""
API routes for the merge service.

Endpoints:
- POST /search - Execute merged search
- GET /search/stream/{searchId} - Stream search results via SSE
- GET /search/{searchId} - Get search status
- GET /downloads/active - Get active downloads
- POST /download - Initiate download
- GET /hooks - List hooks
- POST /hooks - Register hook
"""

import uuid
import logging
import sys
from typing import Optional
from datetime import datetime

sys.path.insert(0, "/config/download-proxy/src")

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import List

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["search"])


# Request/Response models
class SearchRequest(BaseModel):
    """Request model for search endpoint."""

    query: str = Field(..., description="Search query", min_length=1)
    category: str = Field(default="all", description="Category filter")
    limit: int = Field(default=50, description="Maximum results", ge=1, le=100)
    enable_metadata: bool = Field(
        default=True, description="Enable metadata enrichment"
    )
    validate_trackers: bool = Field(default=True, description="Validate tracker health")


class SearchResultResponse(BaseModel):
    """Single search result in response."""

    name: str
    size: str
    seeds: int
    leechers: int
    download_urls: List[str]
    quality: Optional[str] = None
    sources: List[dict] = Field(default_factory=list)


class SearchResponse(BaseModel):
    """Response model for search endpoint."""

    search_id: str
    query: str
    status: str
    results: List[SearchResultResponse] = Field(default_factory=list)
    total_results: int
    merged_results: int
    trackers_searched: List[str] = Field(default_factory=list)
    started_at: str
    completed_at: Optional[str] = None


class DownloadRequest(BaseModel):
    """Request model for download endpoint."""

    result_id: str = Field(..., description="Merged result ID")
    download_urls: List[str] = Field(..., description="URLs to download")


class HookConfig(BaseModel):
    """Hook configuration model."""

    name: str
    event: str  # search_start, search_complete, download_start, etc.
    script_path: str
    enabled: bool = True


# Dependency to get search orchestrator
async def get_orchestrator():
    """Get the search orchestrator from app state."""
    from merge_service.search import SearchOrchestrator

    # This would come from app state in production
    return SearchOrchestrator()


# Search endpoints
@router.post("/search", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    orchestrator=Depends(get_orchestrator),
):
    """
    Execute a merged search across all enabled trackers.

    Returns immediately with search ID. Use /search/stream/{searchId}
    for real-time updates.
    """
    from merge_service.search import SearchResult

    # Execute search
    metadata = await orchestrator.search(
        query=request.query,
        category=request.category,
        enable_metadata=request.enable_metadata,
        validate_trackers=request.validate_trackers,
    )

    # Get actual results - search each tracker directly
    results = []
    for tracker_name in metadata.trackers_searched:
        try:
            tracker = type(
                "TrackerSource",
                (),
                {"name": tracker_name, "url": "https://" + tracker_name + ".org"},
            )()
            search_results = await orchestrator._search_tracker(
                tracker, request.query, request.category
            )
            for r in search_results[: request.limit]:
                formatted_size = _format_size_from_bytes(None, r.size)
                results.append(
                    SearchResultResponse(
                        name=r.name or f"Torrent {r.link.split('?t=')[-1]}"
                        if r.link
                        else "Unknown",
                        size=formatted_size,
                        seeds=r.seeds,
                        leechers=r.leechers,
                        download_urls=[r.link],
                        quality=_detect_quality(r.name, r.size),
                        sources=[
                            {
                                "tracker": r.tracker,
                                "seeds": r.seeds,
                                "leechers": r.leechers,
                            }
                        ],
                    )
                )
        except Exception:
            pass

    # Limit results
    results = results[: request.limit]

    # Build response
    actual_status = "completed" if metadata.total_results > 0 else metadata.status
    return SearchResponse(
        search_id=metadata.search_id,
        query=metadata.query,
        status=actual_status,
        results=results,
        total_results=metadata.total_results,
        merged_results=metadata.merged_results,
        trackers_searched=metadata.trackers_searched,
        started_at=metadata.started_at.isoformat(),
        completed_at=metadata.completed_at.isoformat()
        if metadata.completed_at
        else None,
    )

    # Get actual results from all trackers
    results = []
    for tracker in orchestrator._active_searches.get(metadata.search_id, None):
        if hasattr(tracker, "results"):
            for r in tracker.results[: request.limit]:
                results.append(
                    SearchResultResponse(
                        name=r.name,
                        size=r.size,
                        seeds=r.seeds,
                        leechers=r.leechers,
                        download_urls=[r.link],
                        quality=_detect_quality(r.name, r.size),
                        sources=[
                            {
                                "tracker": r.tracker,
                                "seeds": r.seeds,
                                "leechers": r.leechers,
                            }
                        ],
                    )
                )

    # Limit results
    results = results[: request.limit]

    # Build response
    actual_status = "completed" if metadata.total_results > 0 else metadata.status
    return SearchResponse(
        search_id=metadata.search_id,
        query=metadata.query,
        status=actual_status,
        results=results,
        total_results=metadata.total_results,
        merged_results=metadata.merged_results,
        trackers_searched=metadata.trackers_searched,
        started_at=metadata.started_at.isoformat(),
        completed_at=metadata.completed_at.isoformat()
        if metadata.completed_at
        else None,
    )


def _format_size_from_bytes(_self, size_str: str) -> str:
    """Format bytes to human readable string."""
    try:
        size_bytes = int(size_str)
    except (ValueError, TypeError):
        return size_str

    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def _detect_quality(name: str, size: str) -> str:
    """Detect quality tier based on name and size."""
    if not name and not size:
        return "unknown"

    name_lower = (name or "").lower()

    # Check resolution in name
    if "2160p" in name_lower or "4k" in name_lower:
        return "uhd_4k"
    elif "1080p" in name_lower:
        return "full_hd"
    elif "720p" in name_lower:
        return "hd"
    elif "480p" in name_lower or "dvdr" in name_lower:
        return "sd"

    # Check size as bytes for quality inference
    try:
        size_bytes = int(size)

        if size_bytes >= 40 * 1024**3:  # 40GB+
            return "uhd_4k"
        elif size_bytes >= 10 * 1024**3:  # 10GB+
            return "full_hd"
        elif size_bytes >= 2 * 1024**3:  # 2GB+
            return "hd"
        elif size_bytes >= 500 * 1024**2:  # 500MB+
            return "sd"
    except (ValueError, TypeError):
        # Try parsing as string
        import re

        size_match = re.search(r"([\d.]+)\s*(GB|MB|TB)", size.lower() if size else "")
        if size_match:
            value = float(size_match.group(1))
            unit = size_match.group(2)
            size_bytes = value * (1024**2 if unit == "MB" else 1024**3)

            if size_bytes >= 40 * 1024**3:
                return "uhd_4k"
            elif size_bytes >= 10 * 1024**3:
                return "full_hd"
            elif size_bytes >= 2 * 1024**3:
                return "hd"

    return "unknown"


@router.get("/search/stream/{search_id}")
async def search_stream(search_id: str):
    """
    Stream search results in real-time using Server-Sent Events.

    Connect to this endpoint to receive live updates about search progress
    and results as they come in.
    """
    from fastapi.responses import StreamingResponse
    from .streaming import SSEHandler

    # Would get orchestrator from app state
    from merge_service.search import SearchOrchestrator

    orchestrator = SearchOrchestrator()

    return SSEHandler.create_streaming_response(
        SSEHandler.search_results_stream(search_id, orchestrator)
    )


@router.get("/search/{search_id}", response_model=SearchResponse)
async def get_search(search_id: str):
    """Get search status and results."""
    from merge_service.search import SearchOrchestrator

    orchestrator = SearchOrchestrator()

    metadata = orchestrator.get_search_status(search_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Search not found")

    return SearchResponse(
        search_id=metadata.search_id,
        query=metadata.query,
        status=metadata.status,
        results=[],
        total_results=metadata.total_results,
        merged_results=metadata.merged_results,
        trackers_searched=metadata.trackers_searched,
        started_at=metadata.started_at.isoformat(),
        completed_at=metadata.completed_at.isoformat()
        if metadata.completed_at
        else None,
    )


# Download endpoints
@router.get("/downloads/active")
async def get_active_downloads():
    """Get list of active downloads."""
    # Placeholder - would query qBittorrent API
    return {
        "downloads": [],
        "count": 0,
    }


@router.post("/download")
async def initiate_download(request: DownloadRequest):
    """
    Initiate download of a merged result.

    Wires all download URLs to qBittorrent for maximum availability.
    """
    import os
    import aiohttp

    download_id = str(uuid.uuid4())
    qbit_url = os.getenv("QBITTORRENT_URL", "http://localhost:18085")
    qbit_user = os.getenv("QBITTORRENT_USER", "admin")
    qbit_pass = os.getenv("QBITTORRENT_PASS", "admin")

    results = []

    for url in request.download_urls[:3]:  # Try up to 3 URLs
        try:
            # Check if it's a magnet link
            if url.startswith("magnet:"):
                # Add magnet directly
                async with aiohttp.ClientSession() as session:
                    auth = aiohttp.BasicAuthLogin(qbit_user, qbit_pass)
                    async with session.post(
                        f"{qbit_url}/api/v2/torrents/add",
                        data={"urls": url},
                        auth=auth,
                    ) as resp:
                        if resp.status in (200, 201):
                            results.append({"url": url, "status": "added"})
                        else:
                            results.append(
                                {"url": url, "status": "failed", "code": resp.status}
                            )
            else:
                # Download torrent file first, then add
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            content = await resp.read()
                            files = aiohttp.FormData()
                            files.add_field(
                                "torrentfile",
                                content,
                                filename="download.torrent",
                                content_type="application/x-bittorrent",
                            )
                            auth = aiohttp.BasicAuthLogin(qbit_user, qbit_pass)
                            async with session.post(
                                f"{qbit_url}/api/v2/torrents/add",
                                data=files,
                                auth=auth,
                            ) as add_resp:
                                if add_resp.status in (200, 201):
                                    results.append({"url": url, "status": "added"})
                                else:
                                    results.append(
                                        {
                                            "url": url,
                                            "status": "failed",
                                            "code": add_resp.status,
                                        }
                                    )
                        else:
                            results.append(
                                {"url": url, "status": "failed", "code": resp.status}
                            )
        except Exception as e:
            results.append({"url": url, "status": "error", "message": str(e)})

    added_count = sum(1 for r in results if r.get("status") == "added")

    return {
        "download_id": download_id,
        "status": "initiated" if added_count > 0 else "failed",
        "urls_count": len(request.download_urls),
        "added_count": added_count,
        "results": results,
    }


# Hooks endpoints
@router.get("/hooks")
async def list_hooks():
    """List all registered hooks."""
    return {
        "hooks": [],
        "count": 0,
    }


@router.post("/hooks")
async def register_hook(hook: HookConfig):
    """Register a new hook."""
    # Placeholder - would save hook config
    return {
        "hook_id": str(uuid.uuid4()),
        "name": hook.name,
        "event": hook.event,
        "enabled": hook.enabled,
    }


# Include router in main app
__all__ = ["router"]
