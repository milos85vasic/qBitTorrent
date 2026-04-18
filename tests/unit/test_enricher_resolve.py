"""
Unit tests for MetadataEnricher with mocked APIs.

Tests individual lookup methods directly since resolve() has a fixed API order.
"""

import pytest
import sys
import os
import json
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "download-proxy", "src"))

from merge_service.enricher import MetadataEnricher, MetadataResult


def _make_mock_session(response_data, status=200, method="get"):
    """Create a properly mocked aiohttp session for nested async context managers."""
    mock_response = MagicMock()
    mock_response.status = status
    mock_response.json = AsyncMock(return_value=response_data)
    mock_response.text = AsyncMock(return_value=json.dumps(response_data))

    mock_response_cm = MagicMock()
    mock_response_cm.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response_cm.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    if method == "get":
        mock_session.get = MagicMock(return_value=mock_response_cm)
    elif method == "post":
        mock_session.post = MagicMock(return_value=mock_response_cm)

    mock_session_cm = MagicMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    return mock_session_cm


class TestEnricherLookupOMDb:
    """Test OMDb lookup method."""

    @pytest.fixture
    def enricher(self):
        with patch.dict(os.environ, {"OMDB_API_KEY": "test_key"}):
            return MetadataEnricher()

    @pytest.mark.asyncio
    async def test_lookup_omdb_success(self, enricher):
        """OMDb lookup with valid response."""
        mock_session_cm = _make_mock_session({
            "Title": "The Matrix",
            "Year": "1999",
            "imdbRating": "8.7",
            "Genre": "Action, Sci-Fi",
            "Plot": "A computer hacker learns...",
            "Response": "True",
        })

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            result = await enricher._lookup_omdb("The Matrix")
            assert result is not None
            assert isinstance(result, MetadataResult)
            assert result.title == "The Matrix"
            assert result.source == "OMDb"

    @pytest.mark.asyncio
    async def test_lookup_omdb_no_api_key(self):
        """OMDb lookup without API key returns None."""
        with patch.dict(os.environ, {}, clear=True):
            enricher = MetadataEnricher()
            result = await enricher._lookup_omdb("The Matrix")
            assert result is None

    @pytest.mark.asyncio
    async def test_lookup_omdb_not_found(self, enricher):
        """OMDb lookup with 'False' response returns None."""
        mock_session_cm = _make_mock_session({"Response": "False", "Error": "Movie not found!"})

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            result = await enricher._lookup_omdb("NonExistentMovie12345")
            assert result is None

    @pytest.mark.asyncio
    async def test_lookup_omdb_timeout(self, enricher):
        """OMDb lookup timeout returns None."""
        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_session_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            result = await enricher._lookup_omdb("The Matrix")
            assert result is None


class TestEnricherLookupTMDB:
    """Test TMDB lookup method."""

    @pytest.fixture
    def enricher(self):
        with patch.dict(os.environ, {"TMDB_API_KEY": "test_key"}):
            return MetadataEnricher()

    @pytest.mark.asyncio
    async def test_lookup_tmdb_success(self, enricher):
        """TMDB lookup with valid response."""
        mock_session_cm = _make_mock_session({
            "results": [{
                "title": "The Matrix",
                "release_date": "1999-03-31",
                "vote_average": 8.7,
                "genre_ids": [28, 878],
                "overview": "A computer hacker...",
            }]
        })

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            result = await enricher._lookup_tmdb("The Matrix")
            assert result is not None
            assert isinstance(result, MetadataResult)
            assert result.title == "The Matrix"
            assert result.source == "TMDB"

    @pytest.mark.asyncio
    async def test_lookup_tmdb_no_api_key(self):
        """TMDB lookup without API key returns None."""
        with patch.dict(os.environ, {}, clear=True):
            enricher = MetadataEnricher()
            result = await enricher._lookup_tmdb("The Matrix")
            assert result is None

    @pytest.mark.asyncio
    async def test_lookup_tmdb_empty_results(self, enricher):
        """TMDB lookup with empty results returns None."""
        mock_session_cm = _make_mock_session({"results": []})

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            result = await enricher._lookup_tmdb("NonExistentMovie12345")
            assert result is None


class TestEnricherLookupTVMaze:
    """Test TVMaze lookup method."""

    @pytest.fixture
    def enricher(self):
        return MetadataEnricher()

    @pytest.mark.asyncio
    async def test_lookup_tvmaze_success(self, enricher):
        """TVMaze lookup with valid response."""
        mock_session_cm = _make_mock_session([{
            "show": {
                "name": "Breaking Bad",
                "premiered": "2008-01-20",
                "rating": {"average": 9.5},
                "genres": ["Drama", "Crime"],
                "summary": "A high school chemistry teacher...",
            }
        }])

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            result = await enricher._lookup_tvmaze("Breaking Bad")
            assert result is not None
            assert isinstance(result, MetadataResult)
            assert result.title == "Breaking Bad"
            assert result.source == "TVMaze"

    @pytest.mark.asyncio
    async def test_lookup_tvmaze_empty(self, enricher):
        """TVMaze lookup with empty results returns None."""
        mock_session_cm = _make_mock_session([])

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            result = await enricher._lookup_tvmaze("NonExistentShow12345")
            assert result is None


class TestEnricherLookupAniList:
    """Test AniList lookup method."""

    @pytest.fixture
    def enricher(self):
        return MetadataEnricher()

    @pytest.fixture
    def enricher_with_anilist(self):
        with patch.dict(os.environ, {"ANILIST_CLIENT_ID": "test_id"}):
            return MetadataEnricher()

    @pytest.mark.asyncio
    async def test_lookup_anilist_success(self, enricher_with_anilist):
        """AniList lookup with valid response."""
        mock_session_cm = _make_mock_session({
            "data": {
                "Media": {
                    "id": 1,
                    "title": {"english": "Attack on Titan", "romaji": "Shingeki no Kyojin"},
                    "startDate": {"year": 2013},
                    "coverImage": {"large": "https://example.com/poster.jpg"},
                    "description": "Humans fight giants...",
                }
            }
        }, method="post")

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            result = await enricher_with_anilist._lookup_anilist("Attack on Titan")
            assert result is not None
            assert isinstance(result, MetadataResult)
            assert result.title == "Attack on Titan"
            assert result.source == "AniList"

    @pytest.mark.asyncio
    async def test_lookup_anilist_empty(self, enricher_with_anilist):
        """AniList lookup with empty results returns None."""
        mock_session_cm = _make_mock_session({
            "data": {"Media": None}
        }, method="post")

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            result = await enricher_with_anilist._lookup_anilist("NonExistentAnime12345")
            assert result is None

    @pytest.mark.asyncio
    async def test_lookup_anilist_no_client_id(self):
        """AniList lookup without client ID returns None."""
        with patch.dict(os.environ, {}, clear=True):
            enricher = MetadataEnricher()
            result = await enricher._lookup_anilist("Attack on Titan")
            assert result is None


class TestEnricherLookupMusicBrainz:
    """Test MusicBrainz lookup method."""

    @pytest.fixture
    def enricher(self):
        return MetadataEnricher()

    @pytest.mark.asyncio
    async def test_lookup_musicbrainz_success(self, enricher):
        """MusicBrainz lookup with valid response."""
        mock_session_cm = _make_mock_session({
            "release-groups": [{
                "title": "Abbey Road",
                "first-release-date": "1969-09-26",
                "id": "abc123",
            }]
        })

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            result = await enricher._lookup_musicbrainz("Abbey Road Beatles")
            assert result is not None
            assert isinstance(result, MetadataResult)
            assert result.source == "MusicBrainz"

    @pytest.mark.asyncio
    async def test_lookup_musicbrainz_empty(self, enricher):
        """MusicBrainz lookup with empty results returns None."""
        mock_session_cm = _make_mock_session({"release-groups": []})

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            result = await enricher._lookup_musicbrainz("NonExistentAlbum12345")
            assert result is None


class TestEnricherLookupOpenLibrary:
    """Test OpenLibrary lookup method."""

    @pytest.fixture
    def enricher(self):
        return MetadataEnricher()

    @pytest.mark.asyncio
    async def test_lookup_openlibrary_success(self, enricher):
        """OpenLibrary lookup with valid response."""
        mock_session_cm = _make_mock_session({
            "docs": [{
                "title": "The Great Gatsby",
                "author_name": ["F. Scott Fitzgerald"],
                "first_publish_year": 1925,
            }]
        })

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            result = await enricher._lookup_openlibrary("The Great Gatsby")
            assert result is not None
            assert isinstance(result, MetadataResult)
            assert result.source == "OpenLibrary"

    @pytest.mark.asyncio
    async def test_lookup_openlibrary_empty(self, enricher):
        """OpenLibrary lookup with empty results returns None."""
        mock_session_cm = _make_mock_session({"docs": []})

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            result = await enricher._lookup_openlibrary("NonExistentBook12345")
            assert result is None


class TestEnricherResolve:
    """Test the high-level resolve() method."""

    @pytest.fixture
    def enricher(self):
        return MetadataEnricher()

    @pytest.mark.asyncio
    async def test_resolve_no_apis_available(self, enricher):
        """resolve() with no API keys and no HTTP responses should return None."""
        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(side_effect=Exception("No network"))
        mock_session_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            with patch.dict(os.environ, {}, clear=True):
                enricher = MetadataEnricher()
                result = await enricher.resolve("Some Title")
                assert result is None

    @pytest.mark.asyncio
    async def test_resolve_cache_hit(self, enricher):
        """Cache hit should return cached result without API call."""
        cached = MetadataResult(
            source="test",
            title="Cached Title",
            year=2024,
            content_type="movie",
            genres=["Action"],
            overview="Cached overview",
        )
        enricher._cache["cached title"] = cached

        result = await enricher.resolve("Cached Title")
        assert result is not None
        assert result.title == "Cached Title"

    @pytest.mark.asyncio
    async def test_resolve_tmdb_first(self, enricher):
        """resolve() should try TMDB first and return its result."""
        mock_session_cm = _make_mock_session({
            "results": [{
                "title": "TMDB Movie",
                "release_date": "2024-01-01",
                "vote_average": 7.5,
                "genre_ids": [28],
                "overview": "TMDB overview",
            }]
        })

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            with patch.dict(os.environ, {"TMDB_API_KEY": "test_key"}):
                enricher = MetadataEnricher()
                result = await enricher.resolve("TMDB Movie")
                assert result is not None
                assert result.title == "TMDB Movie"
                assert result.source == "TMDB"

    def test_detect_quality(self, enricher):
        """Quality detection should work for various names."""
        assert enricher.detect_quality("Movie.2024.1080p.BluRay") is not None
        assert enricher.detect_quality("Movie.2024.720p.WEB-DL") is not None
        assert enricher.detect_quality("Movie.2024.2160p.UHD") is not None
        assert enricher.detect_quality("Movie.2024.DVDSCR") is not None

    def test_clear_cache(self, enricher):
        """Clear cache should empty the cache."""
        enricher._cache["test"] = MetadataResult(
            source="test", title="Test", year=2024,
            content_type="movie", genres=["Action"], overview="Test",
        )
        enricher.clear_cache()
        assert len(enricher._cache) == 0

    @pytest.mark.asyncio
    async def test_resolve_invalid_json(self, enricher):
        """Invalid JSON response should be handled gracefully."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(side_effect=json.JSONDecodeError("test", "", 0))

        mock_response_cm = MagicMock()
        mock_response_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response_cm)

        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            with patch.dict(os.environ, {"TMDB_API_KEY": "test_key"}):
                enricher = MetadataEnricher()
                result = await enricher.resolve("Some Movie")
                assert result is None
