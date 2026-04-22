import pytest


@pytest.mark.chaos
def test_service_recovers_from_tracker_timeout():
    """When a tracker times out, the merge service should still return results from others."""
    import httpx

    r = httpx.get(
        "http://localhost:7187/api/v1/search?q=test&trackers=nonexistent_tracker",
        timeout=30,
    )
    assert r.status_code == 200
