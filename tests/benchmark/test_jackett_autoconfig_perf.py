"""Performance baselines for jackett_autoconfig hot paths."""

from __future__ import annotations

import importlib.util
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "download-proxy", "src"))
sys.modules.setdefault("merge_service", type(sys)("merge_service"))
sys.modules["merge_service"].__path__ = [
    os.path.join(PROJECT_ROOT, "download-proxy", "src", "merge_service")
]
_ac_spec = importlib.util.spec_from_file_location(
    "merge_service.jackett_autoconfig",
    os.path.join(PROJECT_ROOT, "download-proxy", "src", "merge_service", "jackett_autoconfig.py"),
)
_ac_mod = importlib.util.module_from_spec(_ac_spec)
sys.modules["merge_service.jackett_autoconfig"] = _ac_mod
_ac_spec.loader.exec_module(_ac_mod)


def test_env_scan_throughput(benchmark):
    big_env = {f"VAR_{i}": str(i) for i in range(1000)}
    big_env.update({
        "RUTRACKER_USERNAME": "u",
        "RUTRACKER_PASSWORD": "p",
        "KINOZAL_USERNAME": "u",
        "KINOZAL_PASSWORD": "p",
    })
    result = benchmark(lambda: _ac_mod._scan_env_credentials(big_env, exclude=set()))
    assert "RUTRACKER" in result
    assert benchmark.stats["mean"] < 0.05  # 50ms hard floor


def test_fuzzy_match_throughput(benchmark):
    catalog = [{"id": f"indexer{i}", "name": f"Indexer{i}"} for i in range(50)]
    catalog.append({"id": "rutracker", "name": "RuTracker"})
    bundles = {f"TRACKER{i}": {"username": "u", "password": "p"} for i in range(10)}
    bundles["RUTRACKER"] = {"username": "u", "password": "p"}
    benchmark(lambda: _ac_mod._match_indexers(bundles, catalog, override={}))
    assert benchmark.stats["mean"] < 0.20  # 200ms hard floor


def test_full_autoconfigure_unreachable_path(benchmark):
    """Failure-fast path must complete quickly even when Jackett is down."""
    import asyncio

    async def run():
        return await _ac_mod.autoconfigure_jackett(
            jackett_url="http://127.0.0.1:1",
            api_key="fake",
            env={"RUTRACKER_USERNAME": "u", "RUTRACKER_PASSWORD": "p"},
            timeout=1.0,
        )

    def runner():
        return asyncio.run(run())

    runner()  # warmup
    result = benchmark(runner)
    assert result.errors  # we expect an error (unreachable)
    assert benchmark.stats["mean"] < 5.0  # well under 60s outer cap
