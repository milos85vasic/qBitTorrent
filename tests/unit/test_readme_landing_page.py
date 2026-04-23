"""Guards the README as the project landing page.

The user directive: "Make sure that all important documentation
(tokens, API keys, props and other too) we can get from main README
page! The landing."

This test asserts the README links to every mandatory doc and the
tokens/keys table, so renaming or removing those docs is immediately
caught.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
README = REPO_ROOT / "README.md"


@pytest.fixture(scope="module")
def readme() -> str:
    assert README.is_file(), README
    return README.read_text()


REQUIRED_LINKS = [
    # Tokens / keys / env vars — the hub doc
    "docs/TOKENS_AND_KEYS.md",
    # Core subsystems
    "docs/USER_MANUAL.md",
    "docs/PLUGINS.md",
    "docs/PLUGIN_TROUBLESHOOTING.md",
    "docs/SECURITY.md",
    "docs/SCANNING.md",
    "docs/QUALITY_STACK.md",
    "docs/OBSERVABILITY.md",
    "docs/PERFORMANCE.md",
    "docs/CONCURRENCY.md",
    "docs/DATA_MODEL.md",
    "docs/TESTING.md",
    "docs/COVERAGE_BASELINE.md",
    "docs/OUT_OF_SANDBOX.md",
    # Architecture
    "docs/architecture/",
    "docs/api/openapi.json",
    # Governance
    "CONTRIBUTING.md",
    "CLAUDE.md",
    "AGENTS.md",
    ".specify/memory/constitution.md",
    # Courses
    "courses/01-operator/",
    "courses/02-plugin-author/",
    "courses/03-contributor/",
    "courses/04-security-ops/",
    # Release / changelog
    "CHANGELOG.md",
    "releases/README.md",
]


@pytest.mark.parametrize("path", REQUIRED_LINKS)
def test_readme_links_required_doc(readme: str, path: str) -> None:
    assert path in readme, f"README.md missing link to {path}"


REQUIRED_REGISTRATION_LINKS = [
    ("RuTracker", "rutracker.org/forum/register.php"),
    ("Kinozal", "kinozal.tv/signup.php"),
    ("NNM-Club", "nnmclub.to/forum/ucp.php"),
    ("IPTorrents", "iptorrents.com"),
    ("Jackett", "github.com/Jackett/Jackett"),
    ("TMDb", "themoviedb.org/signup"),
    ("TVDb", "thetvdb.com/api-information"),
    ("MusicBrainz", "musicbrainz.org/doc/MusicBrainz_API"),
    ("Snyk", "app.snyk.io"),
    ("SonarCloud", "sonarcloud.io/account/security"),
    ("Gitleaks", "gitleaks.io"),
]


@pytest.mark.parametrize("name,host_path", REQUIRED_REGISTRATION_LINKS)
def test_readme_has_registration_link(readme: str, name: str, host_path: str) -> None:
    assert host_path in readme, f"README.md registration table missing {name!r} link (expected {host_path!r})"


def test_readme_explicitly_tags_mandatory_vs_optional(readme: str) -> None:
    # The at-a-glance table + wording must surface the distinction.
    assert "Mandatory" in readme
    assert "Optional" in readme


def test_readme_renders_branding_logo(readme: str) -> None:
    assert "docs/assets/logo.png" in readme, "README should show the branded logo"


def test_readme_has_quickstart_and_documentation_sections(readme: str) -> None:
    for heading in ("Quick start", "Documentation", "Tokens & API keys", "Architecture", "Testing"):
        assert heading in readme, f"README missing top-level section {heading!r}"


def test_tokens_and_keys_doc_covers_every_category() -> None:
    doc = (REPO_ROOT / "docs" / "TOKENS_AND_KEYS.md").read_text()
    for section in (
        "## 1. qBittorrent WebUI",
        "## 2. Private tracker credentials",
        "## 3. Public tracker API keys",
        "## 4. Metadata enrichment APIs",
        "## 5. Security scanner tokens",
        "## 6. Observability endpoints",
        "## 7. Orchestrator tuning",
        "## 8. Data directory",
    ):
        assert section in doc, f"TOKENS_AND_KEYS.md missing section {section!r}"


REQUIRED_TOKEN_ROWS = [
    "RUTRACKER_USERNAME",
    "RUTRACKER_PASSWORD",
    "KINOZAL_USERNAME",
    "KINOZAL_PASSWORD",
    "NNMCLUB_COOKIES",
    "IPTORRENTS_USERNAME",
    "IPTORRENTS_PASSWORD",
    "JACKETT_API_KEY",
    "TMDB_API_KEY",
    "TVDB_API_KEY",
    "MUSICBRAINZ_USER_AGENT",
    "SNYK_TOKEN",
    "SONAR_TOKEN",
    "GITLEAKS_LICENSE",
    "GRAFANA_USER",
    "GRAFANA_PASSWORD",
    "ALLOWED_ORIGINS",
    "MAX_CONCURRENT_TRACKERS",
    "MAX_ACTIVE_SEARCHES",
    "QBITTORRENT_DATA_DIR",
    "PUID",
    "PGID",
]


@pytest.mark.parametrize("var", REQUIRED_TOKEN_ROWS)
def test_tokens_and_keys_doc_documents_var(var: str) -> None:
    doc = (REPO_ROOT / "docs" / "TOKENS_AND_KEYS.md").read_text()
    assert var in doc, f"TOKENS_AND_KEYS.md missing row for {var!r}"
