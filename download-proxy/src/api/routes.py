"""
API routes for the merge service.
"""

import uuid
import logging
import sys
import re
import os
import json
from typing import Optional, List
from datetime import datetime

sys.path.insert(0, "/config/download-proxy/src")

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])

HOOKS_FILE = "/config/download-proxy/hooks.json"


def _load_hooks():
    try:
        if os.path.isfile(HOOKS_FILE):
            with open(HOOKS_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return []


def _save_hooks(hooks):
    try:
        os.makedirs(os.path.dirname(HOOKS_FILE), exist_ok=True)
        with open(HOOKS_FILE, "w") as f:
            json.dump(hooks, f, indent=2)
    except Exception:
        pass


def _get_orchestrator(request: Request):
    from api import orchestrator_instance

    if orchestrator_instance is not None:
        return orchestrator_instance
    from merge_service.search import SearchOrchestrator

    return SearchOrchestrator()


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
    desc_link: Optional[str] = None
    tracker: Optional[str] = None
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


def _parse_size_to_bytes(size_str: str) -> float:
    if not size_str:
        return 0
    try:
        return float(size_str)
    except (ValueError, TypeError):
        pass
    match = re.search(r"([\d.]+)\s*(TB|GB|MB|KB|B)", str(size_str), re.I)
    if match:
        value = float(match.group(1))
        unit = match.group(2).upper()
        mult = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
        return value * mult.get(unit, 1)
    return 0


def _detect_quality(name: str, size: str) -> str:
    nl = (name or "").lower()
    if re.search(r"2160p|4k|uhd", nl):
        return "uhd_4k"
    if re.search(r"1080p|fullhd|fhd|bluray", nl):
        return "full_hd"
    if re.search(r"720p|hdrip|web.dl|webdl", nl):
        return "hd"
    if re.search(r"480p|dvdr|dvdrip|camrip", nl):
        return "sd"
    sb = _parse_size_to_bytes(size)
    if sb >= 40 * 1024**3:
        return "uhd_4k"
    if sb >= 8 * 1024**3:
        return "full_hd"
    if sb >= 2 * 1024**3:
        return "hd"
    if sb >= 300 * 1024**2:
        return "sd"
    return "unknown"


def _to_response(r) -> SearchResultResponse:
    return SearchResultResponse(
        name=r.name,
        size=r.size,
        seeds=r.seeds,
        leechers=r.leechers,
        download_urls=[r.link],
        quality=_detect_quality(r.name, r.size),
        desc_link=r.desc_link,
        tracker=r.tracker,
        sources=[{"tracker": r.tracker, "seeds": r.seeds, "leechers": r.leechers}],
    )


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest, req: Request):
    from merge_service.search import TrackerSource

    orch = _get_orchestrator(req)

    metadata = await orch.search(
        query=request.query,
        category=request.category,
        enable_metadata=request.enable_metadata,
        validate_trackers=request.validate_trackers,
    )

    all_raw = []
    for tn in metadata.trackers_searched:
        try:
            tracker = TrackerSource(name=tn, url=f"https://{tn}.org", enabled=True)
            all_raw.extend(
                await orch._search_tracker(tracker, request.query, request.category)
            )
        except Exception:
            pass

    merged = orch.deduplicator.merge_results(all_raw)
    results = []
    for m in merged:
        best = m.original_results[0] if m.original_results else None
        if not best:
            continue
        resp = _to_response(best)
        resp.sources = [
            {"tracker": r.tracker, "seeds": r.seeds, "leechers": r.leechers}
            for r in m.original_results
        ]
        resp.download_urls = list(dict.fromkeys(r.link for r in m.original_results))
        resp.seeds = m.total_seeds
        resp.leechers = m.total_leechers
        results.append(resp)

    results.sort(key=lambda x: x.seeds, reverse=True)
    results = results[: request.limit]

    return SearchResponse(
        search_id=metadata.search_id,
        query=metadata.query,
        status="completed" if metadata.total_results > 0 else "no_results",
        results=results,
        total_results=metadata.total_results,
        merged_results=len(merged),
        trackers_searched=metadata.trackers_searched,
        started_at=metadata.started_at.isoformat(),
        completed_at=metadata.completed_at.isoformat()
        if metadata.completed_at
        else None,
    )


@router.get("/search/stream/{search_id}")
async def search_stream(search_id: str, req: Request):
    from fastapi.responses import StreamingResponse
    from .streaming import SSEHandler

    orch = _get_orchestrator(req)
    return SSEHandler.create_streaming_response(
        SSEHandler.search_results_stream(search_id, orch)
    )


@router.get("/search/{search_id}", response_model=SearchResponse)
async def get_search(search_id: str, req: Request):
    orch = _get_orchestrator(req)
    metadata = orch.get_search_status(search_id)
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
    import aiohttp

    qbit_url = os.getenv("QBITTORRENT_URL", "http://localhost:18085")
    qbit_user = os.getenv("QBITTORRENT_USER", "admin")
    qbit_pass = os.getenv("QBITTORRENT_PASS", "admin")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{qbit_url}/api/v2/auth/login",
                data={"username": qbit_user, "password": qbit_pass},
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
                                "upspeed": t.get("upspeed", 0),
                                "state": t.get("state", ""),
                                "hash": t.get("hash", ""),
                                "eta": t.get("eta", 8640000),
                            }
                        )
                    return {"downloads": downloads, "count": len(downloads)}
    except Exception as e:
        logger.error(f"Failed to get active downloads: {e}")

    return {"downloads": [], "count": 0, "error": "unavailable"}


@router.post("/download")
async def initiate_download(request: DownloadRequest, req: Request):
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
                data={"username": qbit_user, "password": qbit_pass},
            ) as resp:
                if resp.status != 200:
                    return {
                        "download_id": download_id,
                        "status": "auth_failed",
                        "results": [],
                    }
                cookies = resp.cookies

            for url in request.download_urls[:5]:
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
                                {
                                    "url": url,
                                    "status": "failed",
                                    "detail": text[:200],
                                }
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
    hooks = _load_hooks()
    return {"hooks": hooks, "count": len(hooks)}


@router.post("/hooks")
async def register_hook(hook: HookConfig):
    hooks = _load_hooks()
    new_hook = {
        "hook_id": str(uuid.uuid4()),
        "name": hook.name,
        "event": hook.event,
        "script_path": hook.script_path,
        "enabled": hook.enabled,
        "created_at": datetime.utcnow().isoformat(),
    }
    hooks.append(new_hook)
    _save_hooks(hooks)
    return new_hook


@router.delete("/hooks/{hook_id}")
async def delete_hook(hook_id: str):
    hooks = _load_hooks()
    hooks = [h for h in hooks if h["hook_id"] != hook_id]
    _save_hooks(hooks)
    return {"deleted": True, "hook_id": hook_id}


__all__ = ["router"]
