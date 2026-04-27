"""Read-only endpoints exposing Jackett auto-configuration state."""

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(tags=["jackett"])


@router.get("/jackett/autoconfig/last")
async def get_last_autoconfig(request: Request):
    """Return the most recent autoconfig run summary (redacted).

    404 if autoconfig has not run yet (e.g., no JACKETT_API_KEY set).
    """
    last = getattr(request.app.state, "jackett_autoconfig_last", None)
    if last is None:
        raise HTTPException(status_code=404, detail="autoconfig has not run yet")
    return last.model_dump(mode="json", by_alias=True)
