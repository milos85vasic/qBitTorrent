"""
API endpoints for hook management.

Provides:
- GET /hooks - List all registered hooks
- POST /hooks - Register a new hook
- DELETE /hooks/{hook_id} - Remove a hook
- GET /hooks/logs - Get hook execution logs
"""

import uuid
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional as PyOptional

logger = logging.getLogger(__name__)

router = APIRouter(tags=["hooks"])


# Request/Response models
class HookEventType(str):
    """Hook event types."""

    SEARCH_START = "search_start"
    SEARCH_PROGRESS = "search_progress"
    SEARCH_COMPLETE = "search_complete"
    DOWNLOAD_START = "download_start"
    DOWNLOAD_PROGRESS = "download_progress"
    DOWNLOAD_COMPLETE = "download_complete"
    MERGE_COMPLETE = "merge_complete"
    VALIDATION_COMPLETE = "validation_complete"


class HookCreateRequest(BaseModel):
    """Request to create a new hook."""

    name: str = Field(..., description="Hook name", min_length=1)
    event: str = Field(..., description="Event type to trigger on")
    script_path: str = Field(..., description="Path to executable script")
    enabled: bool = Field(default=True, description="Whether hook is enabled")
    timeout: int = Field(default=30, ge=1, le=300, description="Timeout in seconds")
    environment: dict = Field(default_factory=dict, description="Environment variables")


class HookResponse(BaseModel):
    """Hook configuration response."""

    hook_id: str
    name: str
    event: str
    script_path: str
    enabled: bool
    timeout: int
    created_at: str


class HookExecutionLog(BaseModel):
    """Hook execution log entry."""

    hook_name: str
    event_type: str
    timestamp: str
    duration_seconds: float
    return_code: int
    success: bool
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    error: Optional[str] = None


# In-memory storage (would use database in production)
_hooks: dict[str, dict] = {}
_execution_logs: list[dict] = []


@router.get("", response_model=dict)
async def list_hooks():
    """List all registered hooks."""
    return {
        "hooks": [
            {
                "hook_id": h["hook_id"],
                "name": h["name"],
                "event": h["event"],
                "enabled": h["enabled"],
                "script_path": h["script_path"],
                "timeout": h["timeout"],
                "created_at": h["created_at"],
            }
            for h in _hooks.values()
        ],
        "count": len(_hooks),
    }


@router.post("", response_model=HookResponse)
async def create_hook(request: HookCreateRequest):
    """Register a new hook."""
    # Validate event type
    valid_events = [
        e.value
        for e in [
            HookEventType.SEARCH_START,
            HookEventType.SEARCH_PROGRESS,
            HookEventType.SEARCH_COMPLETE,
            HookEventType.DOWNLOAD_START,
            HookEventType.DOWNLOAD_PROGRESS,
            HookEventType.DOWNLOAD_COMPLETE,
            HookEventType.MERGE_COMPLETE,
            HookEventType.VALIDATION_COMPLETE,
        ]
    ]

    if request.event not in valid_events:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event type. Must be one of: {', '.join(valid_events)}",
        )

    # Create hook
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

    _hooks[hook_id] = hook

    logger.info(f"Created hook: {request.name} ({hook_id})")

    return HookResponse(
        hook_id=hook_id,
        name=hook["name"],
        event=hook["event"],
        script_path=hook["script_path"],
        enabled=hook["enabled"],
        timeout=hook["timeout"],
    )


@router.delete("/{hook_id}")
async def delete_hook(hook_id: str):
    """Delete a hook."""
    if hook_id not in _hooks:
        raise HTTPException(status_code=404, detail="Hook not found")

    hook_name = _hooks[hook_id]["name"]
    del _hooks[hook_id]

    logger.info(f"Deleted hook: {hook_name} ({hook_id})")

    return {"message": "Hook deleted", "hook_id": hook_id}


@router.get("/logs")
async def get_execution_logs(
    limit: int = 50,
    hook_name: Optional[str] = None,
):
    """Get hook execution logs."""
    logs = _execution_logs[-limit:]

    if hook_name:
        logs = [l for l in logs if l.get("hook_name") == hook_name]

    return {
        "logs": logs,
        "count": len(logs),
    }


# Helper functions for dispatching hooks
async def dispatch_event(event_type: str, event_data: dict):
    """Dispatch an event to all registered hooks."""
    from merge_service.hooks import HookEvent, HookEventType, get_dispatcher

    try:
        event_enum = HookEventType(event_type)
    except ValueError:
        logger.warning(f"Unknown event type: {event_type}")
        return

    dispatcher = get_dispatcher()

    hook_event = HookEvent(
        event_type=event_enum,
        search_id=event_data.get("search_id"),
        download_id=event_data.get("download_id"),
        data=event_data,
    )

    await dispatcher.dispatch(hook_event)

    # Update logs
    global _execution_logs
    _execution_logs.extend(dispatcher.get_execution_log()[-10:])


__all__ = ["router"]
