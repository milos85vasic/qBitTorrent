"""
Unit tests for env-driven CORS configuration in the merge-service API.

The production default is ``["http://localhost:7186", "http://localhost:7187"]``.
Operators can override origins via the ``ALLOWED_ORIGINS`` environment variable
(comma-separated list).
"""

from __future__ import annotations

import logging
import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_SRC_PATH = os.path.join(_REPO_ROOT, "download-proxy", "src")
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)


def _purge_api_module() -> None:
    """Drop the api.__init__ module so the next import re-evaluates module-level code."""

    for key in [k for k in list(sys.modules) if k == "api" or k.startswith("api.")]:
        del sys.modules[key]


def _cors_middleware_origins(app) -> list[str]:
    """Inspect FastAPI's user_middleware list to pull out CORS allow_origins."""

    from fastapi.middleware.cors import CORSMiddleware

    for mw in app.user_middleware:
        if mw.cls is CORSMiddleware:
            # Starlette's Middleware wraps kwargs.
            return list(mw.kwargs.get("allow_origins", []))
    raise AssertionError("CORSMiddleware not registered on app")


def test_default_uses_localhost_origins(monkeypatch, caplog):
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    _purge_api_module()

    caplog.set_level(logging.WARNING, logger="api")

    import api

    assert _cors_middleware_origins(api.app) == [
        "http://localhost:7186",
        "http://localhost:7187",
    ]

    wildcards = [
        rec
        for rec in caplog.records
        if rec.levelno == logging.WARNING and "CORS wildcard" in rec.getMessage()
    ]
    assert not wildcards


def test_explicit_origins_are_respected(monkeypatch, caplog):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://a.example,https://b.example")
    _purge_api_module()

    caplog.set_level(logging.WARNING, logger="api")

    import api

    assert _cors_middleware_origins(api.app) == [
        "https://a.example",
        "https://b.example",
    ]
    wildcards = [
        rec
        for rec in caplog.records
        if rec.levelno == logging.WARNING and "CORS wildcard" in rec.getMessage()
    ]
    assert not wildcards, (
        "Did not expect a wildcard warning when ALLOWED_ORIGINS is explicitly set; "
        f"captured: {[r.getMessage() for r in caplog.records]}"
    )


def test_whitespace_is_stripped_and_empties_dropped(monkeypatch):
    monkeypatch.setenv(
        "ALLOWED_ORIGINS",
        "  https://a.example , , https://b.example ,",
    )
    _purge_api_module()

    import api

    assert _cors_middleware_origins(api.app) == [
        "https://a.example",
        "https://b.example",
    ]
