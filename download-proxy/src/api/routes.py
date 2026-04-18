"""
API routes for the merge service.
"""

import uuid
import logging
import sys
import re
import os
import json
import urllib.parse
import aiohttp
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])


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
    enable_metadata: bool = Field(default=True, description="Enable metadata enrichment")
    validate_trackers: bool = Field(default=True, description="Validate tracker health")
    sort_by: str = Field(default="seeds", description="Sort column")
    sort_order: str = Field(default="desc", description="Sort direction: asc or desc")


class SearchResultResponse(BaseModel):
    name: str
    size: str
    seeds: int
    leechers: int
    download_urls: List[str]
    quality: Optional[str] = None
    content_type: Optional[str] = None
    desc_link: Optional[str] = None
    tracker: Optional[str] = None
    sources: List[dict] = Field(default_factory=list)
    metadata: Optional[dict] = None
    freeleech: bool = False


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
    from merge_service.enricher import MetadataEnricher

    enricher = MetadataEnricher()
    quality = enricher.detect_quality(name)
    if quality:
        mapping = {
            "4K": "uhd_4k",
            "1080p": "full_hd",
            "720p": "hd",
            "SD": "sd",
            "BluRay": "full_hd",
            "BDRip": "full_hd",
            "BDRemux": "uhd_4k",
            "WEB-DL": "hd",
            "WEBRip": "hd",
            "HDRip": "hd",
            "HDTV": "hd",
            "DVD": "sd",
            "DVDRip": "sd",
        }
        return mapping.get(quality, "unknown")
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


def _to_response(r, content_type: Optional[str] = None) -> SearchResultResponse:
    return SearchResultResponse(
        name=r.name,
        size=r.size,
        seeds=r.seeds,
        leechers=r.leechers,
        download_urls=[r.link],
        quality=_detect_quality(r.name, r.size),
        content_type=content_type,
        desc_link=r.desc_link,
        tracker=r.tracker,
        sources=[{"tracker": r.tracker, "seeds": r.seeds, "leechers": r.leechers}],
        freeleech=getattr(r, "freeleech", False),
    )


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest, req: Request):
    from .hooks import dispatch_event
    import asyncio

    orch = _get_orchestrator(req)

    await dispatch_event("search_start", {"query": request.query})

    metadata = await orch.search(
        query=request.query,
        category=request.category,
        enable_metadata=False,
        validate_trackers=request.validate_trackers,
    )

    stored = orch._last_merged_results.get(metadata.search_id)
    merged = stored[0] if stored else []
    results = []
    for m in merged:
        best = m.original_results[0] if m.original_results else None
        if not best:
            continue
        content_type = (
            m.canonical_identity.content_type.value
            if m.canonical_identity and m.canonical_identity.content_type
            else None
        )
        resp = _to_response(best, content_type=content_type)
        resp.sources = [{"tracker": r.tracker, "seeds": r.seeds, "leechers": r.leechers} for r in m.original_results]
        resp.download_urls = list(dict.fromkeys(r.link for r in m.original_results))
        resp.seeds = m.total_seeds
        resp.leechers = m.total_leechers
        results.append(resp)

    # Apply sorting
    sort_by = request.sort_by
    sort_order = request.sort_order
    reverse = sort_order == "desc"
    sort_weights = {"unknown": 0, "sd": 1, "hd": 2, "full_hd": 3, "uhd_4k": 4, "uhd_8k": 5}

    def _sort_key(x):
        if sort_by == "name":
            return (x.name or "").lower()
        if sort_by == "type":
            return x.content_type or "unknown"
        if sort_by == "size":
            return _parse_size_to_bytes(x.size)
        if sort_by == "seeds":
            return x.seeds
        if sort_by == "leechers":
            return x.leechers
        if sort_by == "quality":
            return sort_weights.get(x.quality or "unknown", 0)
        if sort_by == "sources":
            return len(x.sources)
        return x.seeds

    results.sort(key=_sort_key, reverse=reverse)
    results = results[: request.limit]

    if request.enable_metadata and hasattr(req.app.state, "enricher"):
        from merge_service.enricher import MetadataEnricher

        enricher: MetadataEnricher = req.app.state.enricher
        for r in results[:10]:
            try:
                meta = await enricher.resolve(r.name)
                if meta:
                    r.metadata = {
                        "source": meta.source,
                        "title": meta.title,
                        "year": meta.year,
                        "content_type": meta.content_type,
                        "poster_url": meta.poster_url,
                        "overview": meta.overview,
                        "genres": meta.genres,
                    }
            except Exception as e:
                logger.debug(f"Metadata enrichment failed for {r.name}: {e}")

    captcha_errors = [e for e in metadata.errors if "captcha" in e.lower()]
    if captcha_errors and not results:
        return JSONResponse(
            status_code=403,
            content={
                "search_id": metadata.search_id,
                "query": metadata.query,
                "status": "captcha_required",
                "results": [],
                "total_results": 0,
                "merged_results": 0,
                "trackers_searched": metadata.trackers_searched,
                "errors": metadata.errors,
                "message": "RuTracker requires CAPTCHA. Use /api/v1/auth/rutracker/captcha to solve it.",
                "started_at": metadata.started_at.isoformat(),
                "completed_at": metadata.completed_at.isoformat() if metadata.completed_at else None,
            },
        )

    response = SearchResponse(
        search_id=metadata.search_id,
        query=metadata.query,
        status="completed" if metadata.total_results > 0 else "no_results",
        results=results,
        total_results=metadata.total_results,
        merged_results=len(merged),
        trackers_searched=metadata.trackers_searched,
        started_at=metadata.started_at.isoformat(),
        completed_at=metadata.completed_at.isoformat() if metadata.completed_at else None,
    )

    await dispatch_event(
        "search_complete",
        {
            "search_id": metadata.search_id,
            "query": metadata.query,
            "total_results": metadata.total_results,
            "merged_results": len(merged),
            "trackers_searched": metadata.trackers_searched,
        },
    )

    return response


@router.get("/search/stream/{search_id}")
async def search_stream(search_id: str, req: Request):
    from fastapi.responses import StreamingResponse
    from .streaming import SSEHandler

    orch = _get_orchestrator(req)
    return SSEHandler.create_streaming_response(
        SSEHandler.search_results_stream(search_id, orch, request=req)
    )


@router.get("/search/{search_id}", response_model=SearchResponse)
async def get_search(search_id: str, req: Request):
    orch = _get_orchestrator(req)
    metadata = orch.get_search_status(search_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Search not found")
    result_resp = []
    stored = orch._last_merged_results.get(search_id)
    if stored:
        merged, all_results = stored
        for m in merged[:50]:
            best = m.original_results[0] if m.original_results else None
            if best:
                ct = m.canonical_identity.content_type.value if m.canonical_identity else None
                r = _to_response(best, ct)
                r.sources = [
                    {"tracker": r.tracker, "seeds": r.seeds, "leechers": r.leechers} for r in m.original_results
                ]
                r.download_urls = list(dict.fromkeys(lnk for lnk in (r.link for r in m.original_results)))
                r.seeds = m.total_seeds
                r.leechers = m.total_leechers
                result_resp.append(r)
    return SearchResponse(
        search_id=metadata.search_id,
        query=metadata.query,
        status=metadata.status,
        results=result_resp,
        total_results=metadata.total_results,
        merged_results=metadata.merged_results,
        trackers_searched=metadata.trackers_searched,
        started_at=metadata.started_at.isoformat(),
        completed_at=metadata.completed_at.isoformat() if metadata.completed_at else None,
    )


@router.post("/search/{search_id}/abort")
async def abort_search(search_id: str, req: Request):
    """Mark a search as aborted so it won't be counted as completed."""
    orch = _get_orchestrator(req)
    if search_id in orch._active_searches:
        orch._active_searches[search_id].status = "aborted"
        return {"search_id": search_id, "status": "aborted"}
    return {"search_id": search_id, "status": "not_found"}


@router.get("/downloads/active")
async def get_active_downloads():
    import aiohttp

    qbit_url = os.getenv("QBITTORRENT_URL", "http://localhost:7185")
    qbit_user = _get_qbit_username()
    qbit_pass = _get_qbit_password()

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{qbit_url}/api/v2/auth/login",
                data={"username": qbit_user, "password": qbit_pass},
            ) as resp:
                login_text = await resp.text()
                if resp.status != 200 or login_text.strip() != "Ok.":
                    return {"downloads": [], "count": 0, "error": "auth failed"}
                cookies = resp.cookies

            async with session.get(f"{qbit_url}/api/v2/torrents/info", cookies=cookies) as resp:
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


@router.post("/auth/qbittorrent")
async def auth_qbittorrent(request: Request):
    import aiohttp
    from pydantic import BaseModel

    class QBitLoginRequest(BaseModel):
        username: str = "admin"
        password: str = "admin"
        save: bool = False

    try:
        data = await request.json()
        req = QBitLoginRequest(**data)
    except Exception:
        req = QBitLoginRequest()

    qbit_url = os.getenv("QBITTORRENT_URL", "http://localhost:7185")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{qbit_url}/api/v2/auth/login",
                data={"username": req.username, "password": req.password},
            ) as resp:
                login_text = await resp.text()
                if resp.status == 200 and login_text.strip() == "Ok.":
                    cookies = resp.cookies
                    async with session.get(f"{qbit_url}/api/v2/app/version", cookies=cookies) as vresp:
                        version = await vresp.text() if vresp.status == 200 else "unknown"

                    if req.save:
                        creds_dir = "/config/download-proxy"
                        os.makedirs(creds_dir, exist_ok=True)
                        with open(f"{creds_dir}/qbittorrent_creds.json", "w") as f:
                            json.dump({"username": req.username, "password": req.password}, f)

                    return {
                        "status": "authenticated",
                        "version": version,
                        "message": "Login successful",
                    }
                else:
                    return {
                        "status": "failed",
                        "error": "Invalid credentials",
                    }
    except Exception as e:
        logger.error(f"qBittorrent auth error: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


def _load_saved_qbit_credentials():
    import os
    import json

    creds_file = "/config/download-proxy/qbittorrent_creds.json"
    if os.path.isfile(creds_file):
        try:
            with open(creds_file, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def _get_qbit_password():
    saved = _load_saved_qbit_credentials()
    if saved:
        return saved.get("password", os.getenv("QBITTORRENT_PASS", "admin"))
    return os.getenv("QBITTORRENT_PASS", "admin")


def _get_qbit_username():
    saved = _load_saved_qbit_credentials()
    if saved:
        return saved.get("username", os.getenv("QBITTORRENT_USER", "admin"))
    return os.getenv("QBITTORRENT_USER", "admin")


TRACKER_DOMAINS = (
    "rutracker.org",
    "rutracker.nl",
    "kinozal.tv",
    "kinozal.guru",
    "nnmclub.to",
    "nnmclub.ro",
    "nnm-club.me",
    "iptorrents.com",
    "iptorrents.me",
)


def _is_tracker_url(url: str) -> Optional[str]:
    from urllib.parse import urlparse

    try:
        host = urlparse(url).hostname or ""
        for domain in TRACKER_DOMAINS:
            if host == domain or host.endswith("." + domain):
                if "rutracker" in domain:
                    return "rutracker"
                if "kinozal" in domain:
                    return "kinozal"
                if "nnmclub" in domain or "nnm-club" in domain:
                    return "nnmclub"
                if "iptorrents" in domain:
                    return "iptorrents"
    except Exception as e:
        logger.debug(f"Could not identify tracker from URL: {e}")
    return None


@router.post("/download")
async def initiate_download(request: DownloadRequest, req: Request):
    import aiohttp
    import tempfile
    from .hooks import dispatch_event

    download_id = str(uuid.uuid4())

    await dispatch_event(
        "download_start",
        {
            "download_id": download_id,
            "result_id": request.result_id,
            "url_count": len(request.download_urls),
        },
    )
    qbit_url = os.getenv("QBITTORRENT_URL", "http://localhost:7185")
    qbit_user = _get_qbit_username()
    qbit_pass = _get_qbit_password()

    results = []

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{qbit_url}/api/v2/auth/login",
                data={"username": qbit_user, "password": qbit_pass},
            ) as resp:
                login_text = await resp.text()
                if resp.status != 200 or login_text.strip() != "Ok.":
                    return {
                        "download_id": download_id,
                        "status": "auth_failed",
                        "results": [],
                    }
                qbit_cookies = resp.cookies

            for url in request.download_urls[:5]:
                try:
                    tracker = _is_tracker_url(url)
                    if tracker:
                        orch = _get_orchestrator(req)
                        torrent_data = await orch.fetch_torrent(tracker, url)
                        if torrent_data is None:
                            results.append(
                                {
                                    "url": url,
                                    "status": "failed",
                                    "detail": "could not fetch torrent file from tracker",
                                }
                            )
                            continue
                        with tempfile.NamedTemporaryFile(suffix=".torrent", delete=False) as tmp:
                            tmp.write(torrent_data)
                            tmp_path = tmp.name
                        try:
                            with open(tmp_path, "rb") as f:
                                form = aiohttp.FormData()
                                form.add_field(
                                    "torrents",
                                    f,
                                    filename=f"{tracker}_{download_id[:8]}.torrent",
                                    content_type="application/x-bittorrent",
                                )
                                async with session.post(
                                    f"{qbit_url}/api/v2/torrents/add",
                                    data=form,
                                    cookies=qbit_cookies,
                                ) as add_resp:
                                    if add_resp.status in (200, 201):
                                        results.append(
                                            {
                                                "url": url,
                                                "status": "added",
                                                "method": "proxy",
                                            }
                                        )
                                    else:
                                        text = await add_resp.text()
                                        results.append(
                                            {
                                                "url": url,
                                                "status": "failed",
                                                "detail": text[:200],
                                            }
                                        )
                        finally:
                            os.unlink(tmp_path)
                    else:
                        async with session.post(
                            f"{qbit_url}/api/v2/torrents/add",
                            data={"urls": url},
                            cookies=qbit_cookies,
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

    await dispatch_event(
        "download_complete",
        {
            "download_id": download_id,
            "result_id": request.result_id,
            "added_count": added_count,
            "total_urls": len(request.download_urls),
        },
    )

    return {
        "download_id": download_id,
        "status": "initiated" if added_count > 0 else "failed",
        "urls_count": len(request.download_urls),
        "added_count": added_count,
        "results": results,
    }


@router.post("/download/file")
async def download_torrent_file(request: DownloadRequest, req: Request):
    """Download the first available .torrent file from the result's URLs."""
    import tempfile
    import aiohttp

    orch = _get_orchestrator(req)

    for url in request.download_urls[:5]:
        try:
            tracker = _is_tracker_url(url)
            if tracker:
                torrent_data = await orch.fetch_torrent(tracker, url)
                if torrent_data:
                    from fastapi.responses import StreamingResponse
                    from io import BytesIO

                    return StreamingResponse(
                        BytesIO(torrent_data),
                        media_type="application/x-bittorrent",
                        headers={
                            "Content-Disposition": f'attachment; filename="{tracker}_{request.result_id}.torrent"'
                        },
                    )
            elif url.startswith("magnet:"):
                # For magnet links, return as a .magnet text file
                from fastapi.responses import PlainTextResponse
                return PlainTextResponse(
                    url,
                    headers={
                        "Content-Disposition": f'attachment; filename="{request.result_id}.magnet"',
                        "Content-Type": "text/plain; charset=utf-8",
                    },
                )
            else:
                # Try to fetch direct URL
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            from fastapi.responses import StreamingResponse
                            from io import BytesIO

                            filename = url.split("/")[-1] or f"{request.result_id}.torrent"
                            return StreamingResponse(
                                BytesIO(data),
                                media_type="application/x-bittorrent",
                                headers={
                                    "Content-Disposition": f'attachment; filename="{filename}"'
                                },
                            )
        except Exception:
            continue

    raise HTTPException(status_code=404, detail="No downloadable torrent file found")


@router.post("/magnet")
async def generate_magnet(request: Request):
    from pydantic import BaseModel

    class MagnetRequest(BaseModel):
        result_id: str
        download_urls: List[str]

    try:
        data = await request.json()
        req = MagnetRequest(**data)
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid request"})

    urls = req.download_urls
    hashes = []
    trackers = set()
    for url in urls:
        m = re.search(r"btih:([a-f0-9]{40}|[a-f0-9]{32})", url, re.I)
        if m:
            hashes.append(m.group(1))
        # Extract trackers from magnet links
        if url.startswith("magnet:"):
            for tr in re.findall(r"tr=([^&]+)", url):
                trackers.add(urllib.parse.unquote(tr))

    name = req.result_id or "download"
    dn = urllib.parse.quote(name)
    xt = "&".join(f"xt=urn:btih:{h}" for h in hashes) if hashes else ""
    # Include source trackers + fallback public trackers
    default_trackers = [
        "udp://tracker.opentrackr.org:1337",
        "udp://tracker.leechers.org:6969",
    ]
    for dt in default_trackers:
        trackers.add(dt)
    tr_params = "&".join(f"tr={urllib.parse.quote(t)}" for t in sorted(trackers))
    magnet = f"magnet:?dn={dn}" + (f"&{xt}" if xt else "")
    if tr_params:
        magnet += "&" + tr_params

    return {"magnet": magnet, "hashes": hashes}


__all__ = ["router"]
