# Pytest configuration and fixtures for merge service tests

import pytest
import os
from unittest.mock import Mock, AsyncMock


@pytest.fixture
def qbittorrent_host():
    """Default qBittorrent host URL"""
    return os.environ.get("QBITTORRENT_HOST", "localhost")


@pytest.fixture
def qbittorrent_port():
    """Default qBittorrent WebUI port"""
    return os.environ.get("QBITTORRENT_PORT", "18085")


@pytest.fixture
def qbittorrent_url(qbittorrent_host, qbittorrent_port):
    """Full qBittorrent WebUI URL"""
    return f"http://{qbittorrent_host}:{qbittorrent_port}"


@pytest.fixture
def mock_qbittorrent_api():
    """Mock qBittorrent API client"""
    api = Mock()
    api.get_torrents = AsyncMock(return_value=[])
    api.add_torrent = AsyncMock(return_value={"hash": "abc123"})
    api.get_torrent_files = AsyncMock(return_value=[])
    return api


@pytest.fixture
def sample_search_result():
    """Sample search result for testing"""
    return {
        "name": "Ubuntu 22.04 LTS",
        "link": "magnet:?xt=urn:btih:abc123",
        "size": "2.5 GB",
        "seeds": "100",
        "leechers": "20",
        "engine_url": "https://example-tracker.com",
        "desc_link": "https://example-tracker.com/details/123",
    }


@pytest.fixture
def sample_merged_result():
    """Sample merged search result for testing"""
    return {
        "canonical_name": "Ubuntu 22.04 LTS",
        "canonical_infohash": "abc123",
        "size": "2.5 GB",
        "sources": [
            {"tracker": "tracker1.com", "seeds": 100, "leechers": 20},
            {"tracker": "tracker2.com", "seeds": 80, "leechers": 15},
        ],
        "total_seeds": 180,
        "total_leechers": 35,
        "download_urls": [
            "magnet:?xt=urn:btih:abc123",
            "https://tracker1.com/download/123",
            "https://tracker2.com/download/456",
        ],
    }
