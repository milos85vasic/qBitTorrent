import sys
import time
import os
from unittest.mock import patch

import pytest

_src = os.path.join(os.path.dirname(__file__), "..", "..", "download-proxy", "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from cachetools import TTLCache  # noqa: E402

from api.auth import (  # noqa: E402
    _PENDING_CAPTCHAS_MAX,
    _PENDING_CAPTCHAS_TTL,
    _pending_captchas,
)


def test_captcha_cache_is_ttlcache():
    assert isinstance(_pending_captchas, TTLCache)


def test_captcha_cache_maxsize_is_bounded():
    assert _pending_captchas.maxsize == _PENDING_CAPTCHAS_MAX
    assert _pending_captchas.maxsize <= 1024


def test_captcha_cache_ttl_is_configured():
    assert _pending_captchas.ttl == _PENDING_CAPTCHAS_TTL
    assert _pending_captchas.ttl == 900


def test_captcha_cache_bounded_under_overflow():
    cache = TTLCache(maxsize=1024, ttl=900)
    for i in range(2000):
        cache[f"token_{i}"] = {"cap_sid": f"sid_{i}", "cap_code_field": "cap_code", "base_url": "https://example.com"}
    assert len(cache) <= 1024


def test_captcha_cache_ttl_eviction():
    cache = TTLCache(maxsize=1024, ttl=0.1)
    cache["token_a"] = {"cap_sid": "sid_a"}
    assert "token_a" in cache
    time.sleep(0.15)
    assert "token_a" not in cache


def test_captcha_cache_env_override_maxsize(monkeypatch):
    monkeypatch.setenv("PENDING_CAPTCHAS_MAX", "512")
    monkeypatch.setenv("PENDING_CAPTCHAS_TTL_SECONDS", "600")
    import importlib
    import api.auth as mod

    importlib.reload(mod)
    try:
        assert mod._PENDING_CAPTCHAS_MAX == 512
        assert mod._PENDING_CAPTCHAS_TTL == 600
    finally:
        importlib.reload(mod)
