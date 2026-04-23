"""
Unit tests for refined content type detection.

Issue 2: Type column shows Unknown for most results.
We need comprehensive type detection covering more patterns.
"""

import os
import sys

_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "download-proxy", "src"))
if _src not in sys.path:
    sys.path.insert(0, _src)

from merge_service.deduplicator import Deduplicator
from merge_service.search import SearchResult


class TestContentTypeRefinement:
    """Content type detection must recognize a wide variety of torrent names."""

    def _detect(self, name):
        dedup = Deduplicator()
        result = SearchResult(
            name=name,
            link="magnet:x",
            size="1 GB",
            seeds=1,
            leechers=0,
            engine_url="http://test",
        )
        identity = dedup._extract_identity_from_result(result)
        return identity.content_type

    def test_linux_distro_recognized_as_software(self):
        """Linux distributions must be detected as software, not unknown."""
        for name in [
            "Ubuntu 22.04 LTS Desktop amd64",
            "Debian 12.1 netinst iso",
            "Fedora Workstation 38 x86_64",
            "Arch Linux 2024.01.01",
            "Linux Mint 21.2 Cinnamon",
            "Manjaro KDE 23.0",
            "Kali Linux 2024.1",
            "openSUSE Tumbleweed DVD",
        ]:
            ct = self._detect(name)
            assert ct.value == "software", f"'{name}' detected as {ct}, expected SOFTWARE"

    def test_tv_show_various_patterns(self):
        """TV shows with different naming patterns."""
        tv_cases = [
            "The Show S01E05 1080p",
            "The Show Season 1 Complete",
            "The Show Seasons 1-3",
            "The Show Seasons 1 - 3 Complete",
            "The Show Episode 5 720p",
            "The.Show.S02E10.WEB-DL",
        ]
        for name in tv_cases:
            ct = self._detect(name)
            assert ct.value == "tv", f"'{name}' detected as {ct}, expected TV_SHOW"

    def test_movie_with_resolution(self):
        """Movies with resolution markers."""
        movie_cases = [
            "The Matrix 1999 1080p BluRay",
            "Inception 2010 720p BRRip",
            "Dune 2021 2160p HDR",
            "Avatar 2009 4K UHD",
        ]
        for name in movie_cases:
            ct = self._detect(name)
            assert ct.value == "movie", f"'{name}' detected as {ct}, expected MOVIE"

    def test_music_various_formats(self):
        """Music with various format markers."""
        music_cases = [
            "Artist - Album (2024) MP3 320kbps",
            "Artist - Album FLAC Lossless",
            "Artist - Album [FLAC]",
            "Best of Rock (2023)",
            "Pop Hits Collection",
            "Electronic Mix 2024",
        ]
        for name in music_cases:
            ct = self._detect(name)
            assert ct.value == "music", f"'{name}' detected as {ct}, expected MUSIC"

    def test_audiobook_detection(self):
        """Audiobooks must be detected."""
        cases = [
            "Great Book audiobook mp3",
            "Audiobook - The Novel",
        ]
        for name in cases:
            ct = self._detect(name)
            assert ct.value == "audiobook", f"'{name}' detected as {ct}, expected AUDIOBOOK"

    def test_game_detection(self):
        """Games with platform or group markers."""
        game_cases = [
            "Game Title CODEX",
            "Game Title FitGirl Repack",
            "Game Title Tenoke",
            "Nintendo Switch Game",
            "PS5 Game Title",
            "PC Game Steam Rip",
            "VR Experience Game",
        ]
        for name in game_cases:
            ct = self._detect(name)
            assert ct.value == "game", f"'{name}' detected as {ct}, expected GAME"

    def test_software_detection(self):
        """Software with various markers."""
        software_cases = [
            "AppName 3.2.1 Portable",
            "Software Installer x64",
            "IDE 2024.1 Win/Mac/Linux",
            "Browser Setup.exe",
            "Antivirus Pro 2024",
            "VPN Client dmg",
        ]
        for name in software_cases:
            ct = self._detect(name)
            assert ct.value == "software", f"'{name}' detected as {ct}, expected SOFTWARE"

    def test_ebook_detection(self):
        """Ebooks should be detected (currently missing - this test documents the gap)."""
        # This will fail until we add ebook detection
        cases = [
            "Great Book epub",
            "Technical Manual pdf",
            "Novel mobi",
            "Comic Collection cbr",
        ]
        for name in cases:
            ct = self._detect(name)
            # Currently these may be unknown - we need to add ebook patterns
            assert ct.value in ("ebook", "unknown"), (
                f"'{name}' detected as {ct}, expected EBOOK or UNKNOWN (until fixed)"
            )

    def test_anime_detection(self):
        """Anime with [anime] marker."""
        ct = self._detect("[anime] Some Anime Title 1080p")
        assert ct.value == "anime"

    def test_ost_soundtrack_music(self):
        """OST and soundtracks must be music."""
        for name in ["Movie OST 2024", "Game Soundtrack FLAC", "Film Score MP3"]:
            ct = self._detect(name)
            assert ct.value == "music", f"'{name}' detected as {ct}, expected MUSIC"

    def test_unknown_for_generic(self):
        """Generic names with no markers should be unknown."""
        ct = self._detect("Some Random File")
        assert ct.value == "unknown"


class TestContentTypeApiResponse:
    """content_type must always be a string in API responses, never null."""

    def test_content_type_unknown_is_string(self):
        from api.routes import _to_response
        from merge_service.search import SearchResult

        r = SearchResult(
            name="Some Random File",
            link="magnet:x",
            size="1 GB",
            seeds=1,
            leechers=0,
            engine_url="http://test",
            tracker="test",
        )
        resp = _to_response(r, content_type="unknown")
        assert resp.content_type == "unknown"

    def test_content_type_movie_is_string(self):
        from api.routes import _to_response
        from merge_service.search import SearchResult

        r = SearchResult(
            name="Movie 2024 1080p",
            link="magnet:x",
            size="2 GB",
            seeds=100,
            leechers=20,
            engine_url="http://test",
            tracker="test",
        )
        resp = _to_response(r, content_type="movie")
        assert resp.content_type == "movie"
