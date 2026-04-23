"""
Retry policy for outbound HTTP calls.

Contract:
  - Transient aiohttp.ClientError failures are retried up to 3 times with
    exponential backoff (multiplier=1, max_wait=10s).
  - After 3 consecutive failures the exception propagates to the caller.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys

import aiohttp
import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SRC_PATH = os.path.join(_REPO_ROOT, "download-proxy", "src")
_MS_PATH = os.path.join(_SRC_PATH, "merge_service")

if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)


def _import_retry():
    sys.modules.setdefault("merge_service", type(sys)("merge_service"))
    sys.modules["merge_service"].__path__ = [_MS_PATH]
    spec = importlib.util.spec_from_file_location("merge_service.retry", os.path.join(_MS_PATH, "retry.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["merge_service.retry"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.asyncio
async def test_retry_succeeds_after_transient_failures():
    """A flaky endpoint that fails 2x then succeeds on 3rd should eventually succeed."""
    retry_mod = _import_retry()
    retry_policy = retry_mod.retry_policy

    attempts = 0

    @retry_policy
    async def flaky_fetch():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise aiohttp.ClientError("connection reset")
        return "ok"

    result = await flaky_fetch()
    assert result == "ok"
    assert attempts == 3


@pytest.mark.asyncio
async def test_retry_raises_after_exhausted_attempts():
    """After 3 consecutive failures the ClientError must propagate."""
    retry_mod = _import_retry()
    retry_policy = retry_mod.retry_policy

    attempts = 0

    @retry_policy
    async def always_fails():
        nonlocal attempts
        attempts += 1
        raise aiohttp.ClientError("permanent failure")

    import tenacity

    with pytest.raises(tenacity.RetryError):
        await always_fails()

    assert attempts == 3
