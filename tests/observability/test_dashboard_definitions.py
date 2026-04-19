"""Guards the Prometheus config + Grafana dashboard JSON we ship.

These are not live scrape tests — they validate the static
configuration files so a typo cannot ship.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
OBSERVABILITY = REPO_ROOT / "observability"
PROM_YML = OBSERVABILITY / "prometheus.yml"
DASH_JSON = OBSERVABILITY / "dashboards" / "merge-search.json"
DASH_PROV = OBSERVABILITY / "dashboards" / "default.yml"
DS_PROV = OBSERVABILITY / "datasources" / "prometheus.yml"

pytestmark = pytest.mark.observability


@pytest.fixture(scope="module")
def prom_yaml() -> str:
    assert PROM_YML.is_file()
    return PROM_YML.read_text()


@pytest.fixture(scope="module")
def merge_dash() -> dict:
    assert DASH_JSON.is_file()
    return json.loads(DASH_JSON.read_text())


def test_prometheus_scrapes_merge_search(prom_yaml: str) -> None:
    assert "job_name: merge-search" in prom_yaml
    assert "/metrics" in prom_yaml
    assert "7187" in prom_yaml


def test_prometheus_scrapes_bridge(prom_yaml: str) -> None:
    assert "job_name: webui-bridge" in prom_yaml
    assert "7188" in prom_yaml


def test_dashboard_has_required_panels(merge_dash: dict) -> None:
    titles = {p["title"] for p in merge_dash.get("panels", [])}
    for required in (
        "Active searches",
        "Tracker requests per second",
        "Search latency (p95)",
        "Circuit breaker state per tracker",
    ):
        assert required in titles, f"merge-search dashboard missing panel {required!r}"


def test_dashboard_references_merge_metrics(merge_dash: dict) -> None:
    all_exprs = []
    for p in merge_dash.get("panels", []):
        for t in p.get("targets", []):
            all_exprs.append(t.get("expr", ""))
    blob = "\n".join(all_exprs)
    for metric in (
        "qbit_merge_active_searches",
        "qbit_merge_tracker_requests_total",
        "qbit_merge_search_duration_seconds_bucket",
        "qbit_merge_circuit_breaker_state",
    ):
        assert metric in blob, f"dashboard does not reference metric {metric!r}"


def test_grafana_dashboards_provisioner_present() -> None:
    assert DASH_PROV.is_file()
    content = DASH_PROV.read_text()
    assert "apiVersion: 1" in content
    assert "providers:" in content


def test_grafana_datasource_provisioner_present() -> None:
    assert DS_PROV.is_file()
    content = DS_PROV.read_text()
    assert "type: prometheus" in content
    assert "url:" in content
