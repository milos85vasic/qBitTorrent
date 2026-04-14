"""
API routes for the merge service.
"""

import uuid
import logging
import sys
import re
from typing import Optional, List

sys.path.insert(0, "/config/download-proxy/src")

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query", min_length=1)
    category: str = Field(default="all", description="Category filter")
    limit: int = Field(default=50, description="Maximum results", ge=1, le=100)
    enable_metadata: bool = Field(
        default=True, description="Enable metadata enrichment"
    )
    validate_trackers: bool = Field(default=True, description="Validate tracker health")


class SearchResultResponse(BaseModel):
    name: str
    size: str
    seeds: int
    leechers: int
    download_urls: List[str]
    quality: Optional[str] = None
    sources: List[dict] = Field(default_factory=list)


class SearchResponse(BaseModel):
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
    result_id: str = Field(..., description="Merged result ID")
    download_urls: List[str] = Field(..., description="URLs to download")


class HookConfig(BaseModel):
    name: str
    event: str
    script_path: str
    enabled: bool = True


async def get_orchestrator():
    from merge_service.search import SearchOrchestrator

    return SearchOrchestrator()


def _parse_size_to_bytes(size_str: str) -> float:
    if not size_str:
        return 0
    try:
        val = float(size_str)
        return val
    except (ValueError, TypeError):
        pass
    match = re.search(r"([\d.]+)\s*(TB|GB|MB|KB|B)", size_str, re.I)
    if match:
        value = float(match.group(1))
        unit = match.group(2).upper()
        multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
        return value * multipliers.get(unit, 1)
    return 0


def _detect_quality(name: str, size: str) -> str:
    name_lower = (name or "").lower()

    if "2160p" in name_lower or "4k" in name_lower or "uhd" in name_lower:
        return "uhd_4k"
    if "1080p" in name_lower or "fullhd" in name_lower or "fhd" in name_lower:
        return "full_hd"
    if "720p" in name_lower:
        return "hd"
    if "480p" in name_lower or "dvdr" in name_lower:
        return "sd"

    size_bytes = _parse_size_to_bytes(size)
    if size_bytes >= 40 * 1024**3:
        return "uhd_4k"
    if size_bytes >= 8 * 1024**3:
        return "full_hd"
    if size_bytes >= 2 * 1024**3:
        return "hd"
    if size_bytes >= 300 * 1024**2:
        return "sd"

    return "unknown"


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest, orchestrator=Depends(get_orchestrator)):
    from merge_service.search import TrackerSource

    metadata = await orchestrator.search(
        query=request.query,
        category=request.category,
        enable_metadata=request.enable_metadata,
        validate_trackers=request.validate_trackers,
    )

    results = []
    for tracker_name in metadata.trackers_searched:
        try:
            tracker = TrackerSource(
                name=tracker_name,
                url=f"https://{tracker_name}.org",
                enabled=True,
            )
            search_results = await orchestrator._search_tracker(
                tracker, request.query, request.category
            )
            for r in search_results:
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
        except Exception:
            pass

    results = sorted(results, key=lambda x: x.seeds, reverse=True)
    results = results[: request.limit]

    return SearchResponse(
        search_id=metadata.search_id,
        query=metadata.query,
        status="completed" if metadata.total_results > 0 else "no_results",
        results=results,
        total_results=metadata.total_results,
        merged_results=metadata.merged_results,
        trackers_searched=metadata.trackers_searched,
        started_at=metadata.started_at.isoformat(),
        completed_at=metadata.completed_at.isoformat()
        if metadata.completed_at
        else None,
    )


@router.get("/search/stream/{search_id}")
async def search_stream(search_id: str):
    from fastapi.responses import StreamingResponse
    from .streaming import SSEHandler
    from merge_service.search import SearchOrchestrator

    orchestrator = SearchOrchestrator()
    return SSEHandler.create_streaming_response(
        SSEHandler.search_results_stream(search_id, orchestrator)
    )


@router.get("/search/{search_id}", response_model=SearchResponse)
async def get_search(search_id: str):
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


@router.get("/downloads/active")
async def get_active_downloads():
    import os
    import aiohttp

    qbit_url = os.getenv("QBITTORRENT_URL", "http://localhost:18085")
    qbit_user = os.getenv("QBITTORRENT_USER", "admin")
    qbit_pass = os.getenv("QBITTORRENT_PASS", "admin")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{qbit_url}/api/v2/auth/login",
                data={
                    "username": qbit_user,
                    "password": qbit_pass,
                },
            ) as resp:
                if resp.status != 200:
                    return {"downloads": [], "count": 0, "error": "auth failed"}
                cookies = resp.cookies

            async with session.get(
                f"{qbit_url}/api/v2/torrents/info", cookies=cookies
            ) as resp:
                if resp.status == 200:
                    torrents = await resp.json()
                    downloads = []
                    for t in torrents:
                        downloads.append(
                            {
                                "name": t.get("name", ""),
                                "size": t.get("size", 0),
                                "progress": round(t.get("progress", 0) * 100, 1),
                                "dlspeed": t.get("dlspeed", 0),
                                "state": t.get("state", ""),
                                "hash": t.get("hash", ""),
                            }
                        )
                    return {"downloads": downloads, "count": len(downloads)}
    except Exception as e:
        logger.error(f"Failed to get active downloads: {e}")

    return {"downloads": [], "count": 0, "error": "unavailable"}


@router.post("/download")
async def initiate_download(request: DownloadRequest):
    import os
    import aiohttp

    download_id = str(uuid.uuid4())
    qbit_url = os.getenv("QBITTORRENT_URL", "http://localhost:18085")
    qbit_user = os.getenv("QBITTORRENT_USER", "admin")
    qbit_pass = os.getenv("QBITTORRENT_PASS", "admin")

    results = []

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{qbit_url}/api/v2/auth/login",
                data={
                    "username": qbit_user,
                    "password": qbit_pass,
                },
            ) as resp:
                if resp.status != 200:
                    return {
                        "download_id": download_id,
                        "status": "auth_failed",
                        "results": [],
                    }
                cookies = resp.cookies

            for url in request.download_urls[:3]:
                try:
                    async with session.post(
                        f"{qbit_url}/api/v2/torrents/add",
                        data={"urls": url},
                        cookies=cookies,
                    ) as resp:
                        if resp.status in (200, 201):
                            results.append({"url": url, "status": "added"})
                        else:
                            text = await resp.text()
                            results.append(
                                {"url": url, "status": "failed", "detail": text[:200]}
                            )
                except Exception as e:
                    results.append({"url": url, "status": "error", "message": str(e)})
    except Exception as e:
        return {
            "download_id": download_id,
            "status": "connection_failed",
            "error": str(e),
        }

    added_count = sum(1 for r in results if r.get("status") == "added")
    return {
        "download_id": download_id,
        "status": "initiated" if added_count > 0 else "failed",
        "urls_count": len(request.download_urls),
        "added_count": added_count,
        "results": results,
    }


@router.get("/hooks")
async def list_hooks():
    return {"hooks": [], "count": 0}


@router.post("/hooks")
async def register_hook(hook: HookConfig):
    return {
        "hook_id": str(uuid.uuid4()),
        "name": hook.name,
        "event": hook.event,
        "enabled": hook.enabled,
    }


__all__ = ["router"]
