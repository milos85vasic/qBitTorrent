"""
Integration tests for the merge service API endpoints.
Uses FastAPI TestClient with mocked SearchOrchestrator.
"""

import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SRC_PATH = os.path.join(_REPO_ROOT, "download-proxy", "src")
sys.path.insert(0, _SRC_PATH)

for _mod_name in list(sys.modules):
    if _mod_name.startswith("merge_service"):
        del sys.modules[_mod_name]

import merge_service as _ms

_ms.__path__.insert(0, os.path.join(_SRC_PATH, "merge_service"))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.routes import router as api_router
from api.hooks import router as hooks_router


def _create_test_client():
    app = FastAPI()

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "service": "merge-search", "version": "1.0.0"}

    app.include_router(api_router, prefix="/api/v1")
    app.include_router(hooks_router, prefix="/api/v1/hooks")
    return TestClient(app)


@pytest.fixture
def client():
    return _create_test_client()


@pytest.fixture(autouse=True)
def _reset_hooks_state(tmp_path, monkeypatch):
    hooks_file = str(tmp_path / "hooks.json")
    monkeypatch.setattr("api.hooks.HOOKS_FILE", hooks_file)
    yield


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["service"] == "merge-search"
        assert "version" in data


class TestSearchEndpoint:
    @patch("api.routes._get_orchestrator")
    def test_search_with_valid_query(self, mock_get_orch, client):
        orch = MagicMock()
        meta = MagicMock()
        meta.search_id = "test-search-123"
        meta.query = "interstellar"
        meta.total_results = 5
        meta.trackers_searched = ["rutracker", "kinozal"]
        meta.started_at = datetime(2025, 1, 1, 12, 0, 0)
        meta.completed_at = datetime(2025, 1, 1, 12, 0, 5)
        orch.search = AsyncMock(return_value=meta)
        orch._search_tracker = AsyncMock(return_value=[])
        orch.deduplicator = MagicMock()
        orch.deduplicator.merge_results.return_value = []
        mock_get_orch.return_value = orch

        with patch.dict(
            "sys.modules",
            {"merge_service.search": MagicMock(TrackerSource=MagicMock())},
        ):
            resp = client.post("/api/v1/search", json={"query": "interstellar"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "interstellar"
        assert data["search_id"] == "test-search-123"
        assert "results" in data
        assert "trackers_searched" in data

    def test_search_with_empty_query_returns_422(self, client):
        resp = client.post("/api/v1/search", json={"query": ""})
        assert resp.status_code == 422

    def test_search_with_missing_body_returns_422(self, client):
        resp = client.post("/api/v1/search")
        assert resp.status_code == 422

    @patch("api.routes._get_orchestrator")
    def test_search_with_defaults(self, mock_get_orch, client):
        orch = MagicMock()
        meta = MagicMock()
        meta.search_id = "abc"
        meta.query = "test"
        meta.total_results = 0
        meta.trackers_searched = []
        meta.started_at = datetime(2025, 1, 1)
        meta.completed_at = datetime(2025, 1, 1)
        orch.search = AsyncMock(return_value=meta)
        orch._search_tracker = AsyncMock(return_value=[])
        orch.deduplicator = MagicMock()
        orch.deduplicator.merge_results.return_value = []
        mock_get_orch.return_value = orch

        with patch.dict(
            "sys.modules",
            {"merge_service.search": MagicMock(TrackerSource=MagicMock())},
        ):
            resp = client.post("/api/v1/search", json={"query": "test"})

        assert resp.status_code == 200


class TestSearchByIdEndpoint:
    @patch("api.routes._get_orchestrator")
    def test_get_unknown_search_returns_404(self, mock_get_orch, client):
        orch = MagicMock()
        orch.get_search_status.return_value = None
        mock_get_orch.return_value = orch

        resp = client.get("/api/v1/search/nonexistent-id")
        assert resp.status_code == 404

    @patch("api.routes._get_orchestrator")
    def test_get_existing_search_returns_200(self, mock_get_orch, client):
        orch = MagicMock()
        meta = MagicMock()
        meta.search_id = "known-id"
        meta.query = "ubuntu"
        meta.status = "completed"
        meta.total_results = 3
        meta.merged_results = 2
        meta.trackers_searched = ["rutracker"]
        meta.started_at = datetime(2025, 1, 1, 12, 0, 0)
        meta.completed_at = datetime(2025, 1, 1, 12, 0, 5)
        orch.get_search_status.return_value = meta
        mock_get_orch.return_value = orch

        resp = client.get("/api/v1/search/known-id")
        assert resp.status_code == 200
        data = resp.json()
        assert data["search_id"] == "known-id"
        assert data["status"] == "completed"


class TestHooksEndpoint:
    def test_list_hooks_empty(self, client):
        resp = client.get("/api/v1/hooks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["hooks"] == []
        assert data["count"] == 0

    def test_create_hook_returns_hook_id(self, client):
        hook_data = {
            "name": "test-hook",
            "event": "search_complete",
            "script_path": "/tmp/test.sh",
            "enabled": True,
        }
        resp = client.post("/api/v1/hooks", json=hook_data)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "test-hook"
        assert data["event"] == "search_complete"
        assert "hook_id" in data

    def test_create_hook_any_event_accepted(self, client):
        hook_data = {
            "name": "custom-hook",
            "event": "custom_event",
            "script_path": "/tmp/custom.sh",
        }
        resp = client.post("/api/v1/hooks", json=hook_data)
        assert resp.status_code == 400

    def test_list_hooks_after_create(self, client):
        hook_data = {
            "name": "my-hook",
            "event": "download_complete",
            "script_path": "/tmp/dl.sh",
        }
        client.post("/api/v1/hooks", json=hook_data)
        resp = client.get("/api/v1/hooks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["hooks"][0]["name"] == "my-hook"

    def test_delete_hook(self, client):
        hook_data = {
            "name": "to-delete",
            "event": "search_complete",
            "script_path": "/tmp/del.sh",
        }
        create_resp = client.post("/api/v1/hooks", json=hook_data)
        hook_id = create_resp.json()["hook_id"]

        resp = client.delete(f"/api/v1/hooks/{hook_id}")
        assert resp.status_code == 200
        assert resp.json()["hook_id"] == hook_id

        list_resp = client.get("/api/v1/hooks")
        assert list_resp.json()["count"] == 0

    def test_delete_nonexistent_hook_returns_404(self, client):
        resp = client.delete("/api/v1/hooks/no-such-hook")
        assert resp.status_code == 404

    def test_create_hook_missing_name_returns_422(self, client):
        resp = client.post(
            "/api/v1/hooks",
            json={"event": "search_complete", "script_path": "/tmp/a.sh"},
        )
        assert resp.status_code == 422

    def test_create_hook_returns_created_at(self, client):
        hook_data = {
            "name": "dated-hook",
            "event": "merge_complete",
            "script_path": "/tmp/merge.sh",
        }
        resp = client.post("/api/v1/hooks", json=hook_data)
        assert resp.status_code == 200
        data = resp.json()
        assert "created_at" in data
        assert data["enabled"] is True

    def test_hook_lifecycle_create_list_delete(self, client):
        hooks_to_create = [
            {"name": "hook-a", "event": "search_start", "script_path": "/tmp/a.sh"},
            {"name": "hook-b", "event": "download_start", "script_path": "/tmp/b.sh"},
        ]
        created_ids = []
        for h in hooks_to_create:
            r = client.post("/api/v1/hooks", json=h)
            assert r.status_code == 200
            created_ids.append(r.json()["hook_id"])

        list_resp = client.get("/api/v1/hooks")
        assert list_resp.json()["count"] == 2

        for hid in created_ids:
            del_resp = client.delete(f"/api/v1/hooks/{hid}")
            assert del_resp.status_code == 200

        assert client.get("/api/v1/hooks").json()["count"] == 0
