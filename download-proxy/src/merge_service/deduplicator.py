"""
Tiered matching engine for deduplicating search results across trackers.

Matching tiers (in order of priority):
1. Metadata match (via external APIs - OMDb, TMDB, etc.)
2. Hash match (infohash comparison)
3. Name + size match (exact name and size)
4. Name similarity match (fuzzy matching via Levenshtein)
"""

import re
from typing import List, Optional, Tuple
from dataclasses import dataclass

try:
    import Levenshtein

    LEV_AVAILABLE = True
except ImportError:
    LEV_AVAILABLE = False

from .search import (
    SearchResult,
    MergedResult,
    CanonicalIdentity,
    ContentType,
    QualityTier,
)


@dataclass
class MatchResult:
    """Result of a match operation."""

    is_match: bool
    confidence: float  # 0.0 to 1.0
    tier: int  # 1-4 (1 = highest priority)
    reason: str


class Deduplicator:
    """Tiered matching engine for deduplicating search results."""

    # Configuration
    SIZE_TOLERANCE_MB = 50  # Size tolerance in MB for "exact" match
    SIMILARITY_THRESHOLD = 0.85  # Minimum similarity for fuzzy match

    def __init__(self):
        self._merged_groups: List[MergedResult] = []

    def merge_results(self, results: List[SearchResult]) -> List[MergedResult]:
        """
        Merge duplicate results from multiple trackers.

        Args:
            results: List of SearchResult objects from all trackers

        Returns:
            List of MergedResult objects (deduplicated)
        """
        self._merged_groups = []
        unmatched = list(results)

        # Sort by seed count (higher seeds = more likely to be canonical)
        unmatched.sort(key=lambda r: r.seeds, reverse=True)

        while unmatched:
            # Take the first unmatched result as the seed for a new group
            seed = unmatched.pop(0)
            merged = self._create_merged_result(seed)

            # Find all matches for this seed
            remaining = []
            for result in unmatched:
                match = self._check_match(seed, result)
                if match.is_match:
                    merged.add_source(result)
                else:
                    remaining.append(result)

            unmatched = remaining
            self._merged_groups.append(merged)

        return self._merged_groups

    def _create_merged_result(self, seed: SearchResult) -> MergedResult:
        """Create a new merged result from a seed search result."""
        identity = self._extract_identity_from_result(seed)
        merged = MergedResult(canonical_identity=identity, download_urls=[seed.link])
        merged.add_source(seed)
        return merged

    def _extract_identity_from_result(self, result: SearchResult) -> CanonicalIdentity:
        """Extract canonical identity from a search result."""
        identity = CanonicalIdentity(title=result.name)

        # Extract year from name (e.g., "Movie Title 2023")
        year_match = re.search(r"\b(19|20)\d{2}\b", result.name)
        if year_match:
            identity.year = int(year_match.group())

        # Extract season/episode for TV shows
        season_ep = re.search(r"[Ss](\d+)[Ee](\d+)", result.name)
        if season_ep:
            identity.season = int(season_ep.group(1))
            identity.episode = int(season_ep.group(2))
            identity.content_type = ContentType.TV_SHOW

        # Extract resolution
        resolution = re.search(r"(720p|1080p|2160p|4k|8k)", result.name, re.I)
        if resolution:
            identity.resolution = resolution.group().lower()

        # Extract codec
        codec = re.search(r"(x264|x265|hevc|h264|h265|xvid|divx)", result.name, re.I)
        if codec:
            identity.codec = codec.group().lower()

        return identity

    def _check_match(self, seed: SearchResult, candidate: SearchResult) -> MatchResult:
        """Check if candidate matches the seed result."""

        if self._is_cross_tracker_freeleech_conflict(seed, candidate):
            return MatchResult(
                is_match=False, confidence=0.0, tier=4, reason="non-freeleech iptorrents vs other tracker"
            )

        # Tier 1: Metadata match (canonical identity comparison)
        id_a = self._extract_identity_from_result(seed)
        id_b = self._extract_identity_from_result(candidate)
        if self._compare_identities(id_a, id_b):
            return MatchResult(is_match=True, confidence=0.99, tier=1, reason="metadata identity match")

        # Tier 2: Hash match (infohash)
        # Compare infohashes if available
        if self._compare_hashes(seed, candidate):
            return MatchResult(is_match=True, confidence=1.0, tier=2, reason="infohash match")

        # Tier 3: Name + size exact match
        if self._compare_name_and_size(seed, candidate):
            return MatchResult(is_match=True, confidence=0.95, tier=3, reason="name+size match")

        # Tier 4: Fuzzy name similarity
        similarity = self._calculate_similarity(seed.name, candidate.name)
        if similarity >= self.SIMILARITY_THRESHOLD:
            return MatchResult(
                is_match=True,
                confidence=similarity,
                tier=4,
                reason=f"fuzzy match ({similarity:.2f})",
            )

        return MatchResult(is_match=False, confidence=0.0, tier=4, reason="no match")

    def _compare_hashes(self, a: SearchResult, b: SearchResult) -> bool:
        """Compare infohashes from magnet links."""
        hash_a = self._extract_infohash(a.link)
        hash_b = self._extract_infohash(b.link)

        if hash_a and hash_b:
            return hash_a.lower() == hash_b.lower()
        return False

    def _extract_infohash(self, link: str) -> Optional[str]:
        """Extract infohash from a magnet link or URL."""
        if not link:
            return None

        # Magnet link format: magnet:?xt=urn:btih:HASH
        if link.startswith("magnet:"):
            match = re.search(r"xt=urn:btih:([a-fA-F0-9]{32,40})", link)
            if match:
                return match.group(1)

        return None

    def _compare_name_and_size(self, a: SearchResult, b: SearchResult) -> bool:
        """Check if two results have matching names and sizes."""
        # Normalize names for comparison
        name_a = self._normalize_name(a.name)
        name_b = self._normalize_name(b.name)

        if name_a != name_b:
            return False

        # Compare sizes (with tolerance)
        size_a = self._parse_size(a.size)
        size_b = self._parse_size(b.size)

        if size_a is None or size_b is None:
            return False

        diff_mb = abs(size_a - size_b) / (1024 * 1024)
        return diff_mb <= self.SIZE_TOLERANCE_MB

    def _normalize_name(self, name: str) -> str:
        """Normalize a torrent name for comparison."""
        # Remove year, resolution, codec, group info for cleaner comparison
        normalized = re.sub(r"\s*\d{4}\s*", " ", name)  # Remove year
        normalized = re.sub(r"\s*(720p|1080p|2160p|4k|8k)\s*", " ", normalized, flags=re.I)  # Remove resolution
        normalized = re.sub(r"\s*(x264|x265|hevc|h264|h265|xvid|divx)\s*", " ", normalized, flags=re.I)  # Remove codec
        normalized = re.sub(r"\s*\[.*?\]\s*", " ", normalized)  # Remove group brackets
        normalized = re.sub(r"\s+", " ", normalized).strip().lower()
        return normalized

    def _parse_size(self, size_str: str) -> Optional[float]:
        """Parse size string to bytes."""
        if not size_str:
            return None

        size_str = size_str.strip().upper()

        # Match size unit and value
        match = re.match(r"([\d.]+)\s*(GB|MB|KB|TB|B)", size_str)
        if not match:
            return None

        value = float(match.group(1))
        unit = match.group(2)

        multipliers = {
            "B": 1,
            "KB": 1024,
            "MB": 1024**2,
            "GB": 1024**3,
            "TB": 1024**4,
        }

        return value * multipliers.get(unit, 1)

    def _calculate_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two names using Levenshtein distance."""
        if not LEV_AVAILABLE:
            # Fallback to simple character overlap
            set1 = set(name1.lower().split())
            set2 = set(name2.lower().split())
            if not set1 or not set2:
                return 0.0
            return len(set1 & set2) / len(set1 | set2)

        # Use Levenshtein ratio
        return Levenshtein.ratio(name1.lower(), name2.lower())

    def _compare_identities(self, a: CanonicalIdentity, b: CanonicalIdentity) -> bool:
        """Compare two canonical identities for Tier 1 match."""
        if a.title and b.title:
            norm_a = self._normalize_name(a.title)
            norm_b = self._normalize_name(b.title)
            if not norm_a or not norm_b:
                return False
            sim = self._calculate_similarity(norm_a, norm_b)
            if sim < 0.80:
                return False
        else:
            return False

        if a.year and b.year and a.year != b.year:
            return False

        if a.content_type and b.content_type and a.content_type != b.content_type:
            return False

        if a.season is not None and b.season is not None and a.season != b.season:
            return False

        if a.episode is not None and b.episode is not None and a.episode != b.episode:
            return False

        return True

    def set_canonical_identity(self, merged: MergedResult, identity: CanonicalIdentity):
        """Update the canonical identity for a merged result (after metadata enrichment)."""
        merged.canonical_identity = identity

    def _is_cross_tracker_freeleech_conflict(self, a: SearchResult, b: SearchResult) -> bool:
        """Prevent merging non-freeleech IPTorrents results with other trackers."""
        if a.tracker == "iptorrents" and b.tracker != "iptorrents":
            if not a.freeleech:
                return True
        if b.tracker == "iptorrents" and a.tracker != "iptorrents":
            if not b.freeleech:
                return True
        return False
