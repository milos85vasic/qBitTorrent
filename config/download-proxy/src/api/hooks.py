"""
API endpoints for hook management.

Single source of truth for hook CRUD + event dispatch.
Uses JSON file persistence at /config/download-proxy/hooks.json.
"""

import os
import json
import uuid
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["hooks"])

HOOKS_FILE = "/config/download-proxy/hooks.json"
LOGS_MAX = 200

VALID_EVENTS = [
    "search_start",
    "search_progress",
    "search_complete",
    "download_start",
    "download_progress",
    "download_complete",
    "merge_complete",
    "validation_complete",
]


class HookCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    event: str = Field(...)
    script_path: str = Field(...)
    enabled: bool = True
    timeout: int = Field(default=30, ge=1, le=300)
    environment: dict = Field(default_factory=dict)


class HookResponse(BaseModel):
    hook_id: str
    name: str
    event: str
    script_path: str
    enabled: bool
    timeout: int
    created_at: str


_execution_logs: list[dict] = []


def _load_hooks() -> list[dict]:
    try:
        if os.path.isfile(HOOKS_FILE):
            with open(HOOKS_FILE) as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load hooks: {e}")
    return []


def _save_hooks(hooks: list[dict]):
    try:
        os.makedirs(os.path.dirname(HOOKS_FILE), exist_ok=True)
        with open(HOOKS_FILE, "w") as f:
            json.dump(hooks, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save hooks: {e}")


@router.get("")
async def list_hooks():
    hooks = _load_hooks()
    return {"hooks": hooks, "count": len(hooks)}


@router.post("", response_model=HookResponse)
async def create_hook(request: HookCreateRequest):
    if request.event not in VALID_EVENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event type. Must be one of: {', '.join(VALID_EVENTS)}",
        )

    hook_id = str(uuid.uuid4())
    hook = {
        "hook_id": hook_id,
        "name": request.name,
        "event": request.event,
        "script_path": request.script_path,
        "enabled": request.enabled,
        "timeout": request.timeout,
        "environment": request.environment,
        "created_at": datetime.utcnow().isoformat(),
    }

    hooks = _load_hooks()
    hooks.append(hook)
    _save_hooks(hooks)

    logger.info(f"Created hook: {request.name} ({hook_id})")

    return HookResponse(
        hook_id=hook_id,
        name=hook["name"],
        event=hook["event"],
        script_path=hook["script_path"],
        enabled=hook["enabled"],
        timeout=hook["timeout"],
        created_at=hook["created_at"],
    )


@router.delete("/{hook_id}")
async def delete_hook(hook_id: str):
    hooks = _load_hooks()
    original_len = len(hooks)
    hooks = [h for h in hooks if h["hook_id"] != hook_id]
    if len(hooks) == original_len:
        raise HTTPException(status_code=404, detail="Hook not found")
    _save_hooks(hooks)
    logger.info(f"Deleted hook: {hook_id}")
    return {"message": "Hook deleted", "hook_id": hook_id}


@router.get("/logs")
async def get_execution_logs(limit: int = 50, hook_name: Optional[str] = None):
    logs = _execution_logs[-limit:]
    if hook_name:
        logs = [l for l in logs if l.get("hook_name") == hook_name]
    return {"logs": logs, "count": len(logs)}


async def dispatch_event(event_type: str, event_data: dict):
    """Dispatch an event to all registered hooks."""
    from merge_service.hooks import HookEvent, HookEventType, get_dispatcher

    try:
        event_enum = HookEventType(event_type)
    except ValueError:
        logger.warning(f"Unknown event type: {event_type}")
        return

    dispatcher = get_dispatcher()

    hooks = _load_hooks()
    for h in hooks:
        if h.get("event") == event_type and h.get("enabled", True):
            from merge_service.hooks import HookConfig

            cfg = HookConfig(
                name=h["name"],
                event=event_enum,
                script_path=h["script_path"],
                enabled=True,
                timeout=h.get("timeout", 30),
                environment=h.get("environment", {}),
            )
            dispatcher.register_hook(cfg)

    hook_event = HookEvent(
        event_type=event_enum,
        search_id=event_data.get("search_id"),
        download_id=event_data.get("download_id"),
        data=event_data,
    )

    await dispatcher.dispatch(hook_event)

    global _execution_logs
    new_logs = dispatcher.get_execution_log()
    _execution_logs.extend(new_logs)
    if len(_execution_logs) > LOGS_MAX:
        _execution_logs[:] = _execution_logs[-LOGS_MAX:]


__all__ = ["router", "dispatch_event"]
