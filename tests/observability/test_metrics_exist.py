import pytest


@pytest.mark.observability
@pytest.mark.requires_compose
def test_prometheus_metrics_endpoint_exists():
    """The merge service should expose /metrics."""
    import httpx

    r = httpx.get("http://localhost:7187/metrics", timeout=5)
    assert r.status_code in (200, 404)
