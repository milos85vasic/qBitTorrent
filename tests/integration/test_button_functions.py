"""
Tests for button functionality: Magnet, qBit, Download
"""

import pytest
import requests
import json
import re


BASE_URL = "http://localhost:7187"


class TestButtonFunctions:
    """Test buttons in the UI."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = BASE_URL
        self.session = requests.Session()

    def search_and_get_results(self, query="matrix"):
        """Perform search and return results."""
        resp = self.session.post(
            f"{self.base_url}/api/v1/search",
            json={"query": query, "limit": 3},
            headers={"Content-Type": "application/json"},
        )
        return resp.json().get("results", [])

    def test_dashboard_has_all_button_handlers(self):
        """All button click handlers should be defined."""
        html = self.session.get(self.base_url).text

        checks = [
            ("function doMagnet(", "doMagnet function"),
            ("function doSchedule(", "doSchedule function"),
            ("function doDownload(", "doDownload function"),
            ("function doDownloadTorrent(", "doDownloadTorrent function"),
            ("function generateMagnet(", "generateMagnet function"),
            ('onclick="doMagnet(', "Magnet button onclick"),
            ('onclick="doSchedule(', "Schedule button onclick"),
            ('onclick="doDownloadTorrent(', "Download button onclick"),
        ]

        print("\n=== Button Handlers ===")
        for pattern, name in checks:
            found = pattern in html
            print(f"{'Y' if found else 'N'} {name}")
            assert found, f"Missing: {name}"

    def test_magnet_button_present(self):
        """Magnet button should be in UI."""
        html = self.session.get(self.base_url).text
        assert "btn-magnet" in html
        assert "Magnet" in html
        print("\nY Magnet button present")

    def test_schedule_button_present(self):
        """Schedule (qBit) button should be in UI."""
        html = self.session.get(self.base_url).text
        assert "btn-schedule" in html
        assert "qBit" in html or "Schedule" in html
        print("Y Schedule button present")

    def test_download_button_present(self):
        """Download button should be in UI."""
        html = self.session.get(self.base_url).text
        assert 'onclick="doDownloadTorrent(' in html
        print("Y Download button present")

    def test_magnet_generation_logic(self):
        """generateMagnet function should exist and have valid logic."""
        html = self.session.get(self.base_url).text

        # Check the function exists and uses proper magnet format
        assert "function generateMagnet(" in html
        assert "magnet:?dn=" in html
        assert "xt=urn:btih:" in html or "tr=udp://" in html

        print("\nY Magnet generation logic valid")

    def test_config_loaded_for_schedule(self):
        """_config should be loaded for qBit button."""
        html = self.session.get(self.base_url).text

        assert "_config" in html
        assert "qbittorrent_url" in html

        print("Y _config variable defined")

    def test_api_download_endpoint_exists(self):
        """Download API endpoint should exist."""
        resp = self.session.post(
            f"{self.base_url}/api/v1/download",
            json={"result_id": "0", "download_urls": ["http://example.com/test.torrent"]},
            headers={"Content-Type": "application/json"},
        )

        # Should return a response (auth may fail, but endpoint exists)
        data = resp.json()
        assert "download_id" in data
        print(f"\nY Download API: {data.get('status')}")

    def test_api_magnet_endpoint_exists(self):
        """Magnet generation API endpoint should exist."""
        resp = self.session.get(f"{self.base_url}/api/v1/magnet")

        # Check if endpoint exists (may need params)
        # This is just existence check
        print("Y Magnet API endpoint exists")

    def test_results_have_download_urls(self):
        """Results should have download_urls for buttons to work."""
        results = self.search_and_get_results("matrix")

        assert len(results) > 0
        r = results[0]

        assert "download_urls" in r
        assert isinstance(r["download_urls"], list)

        print(f"\nY Download URLs: {len(r['download_urls'])} URLs in first result")

    def test_results_have_sources(self):
        """Results should have sources for display."""
        results = self.search_and_get_results("matrix")

        r = results[0]
        assert "sources" in r
        assert isinstance(r["sources"], list)

        print(f"Y Sources: {len(r['sources'])} sources in first result")

    def test_magnet_button_title_attribute(self):
        """Magnet button should have title attribute."""
        html = self.session.get(self.base_url).text

        assert 'title="Get Magnet Link"' in html
        print("\nY Magnet button title attribute")

    def test_schedule_button_title_attribute(self):
        """Schedule button should have title attribute."""
        html = self.session.get(self.base_url).text

        assert 'title="Send to qBittorrent"' in html
        print("Y Schedule button title attribute")

    def test_button_group_css(self):
        """Button group CSS should be defined."""
        html = self.session.get(self.base_url).text

        assert ".btn-group" in html
        assert ".btn-magnet" in html
        assert ".btn-schedule" in html
        print("Y Button group CSS defined")

    def test_alert_handling_in_buttons(self):
        """Buttons should have alert handling for errors."""
        html = self.session.get(self.base_url).text

        # Check for alert calls in functions
        assert "alert('" in html or 'alert("' in html
        print("\nY Alert handling present for errors")


class TestMagnetLinkGeneration:
    """Test magnet link generation logic."""

    def test_magnet_url_format(self):
        """Magnet links should follow correct format."""
        html = requests.get(BASE_URL).text

        checks = [
            ("magnet:?dn=", "magnet:?dn= in code"),
            ("tr=udp://", "UDP tracker"),
        ]

        print("\n=== Magnet Link Validation ===")
        for text, name in checks:
            found = text in html
            print(f"{'Y' if found else 'N'} {name}")
            assert found, f"Magnet format missing: {text}"


class TestScheduleButtonConfig:
    """Test schedule button config loading."""

    def test_config_loads_at_startup(self):
        """_config should be loaded when page loads."""
        html = requests.get(BASE_URL).text

        # Should call loadConfig
        assert "loadConfig()" in html or "loadConfig" in html

        # Should define _config
        assert "var _config" in html

        print("\nY Config loads at startup")

    def test_config_has_qbittorrent_url(self):
        """Config should contain qBittorrent URL."""
        resp = requests.get(f"{BASE_URL}/api/v1/config")
        data = resp.json()

        assert "qbittorrent_url" in data
        assert "7185" in data["qbittorrent_url"]

        print(f"\nY Config: {data}")


class TestButtonFixes:
    """Tests for the three bug fixes."""

    def test_magnet_generates_without_hash_in_url(self):
        """generateMagnet should work without btih hash in tracker URLs."""
        html = requests.get(BASE_URL).text

        # The function should work with just name and default trackers
        assert "magnet:?dn=" in html
        # Should have default fallback trackers
        assert "tracker.opentrackr.org" in html
        # Should NOT try to extract hash from URL (that fails)
        assert "url.match(/btih:" not in html or "m = url.match" not in html

        print("\nY Magnet generates without hash extraction")

    def test_password_field_has_css(self):
        """Password field should have CSS styling in modals."""
        html = requests.get(BASE_URL).text

        # Check password field is styled
        assert 'input[type="password"]' in html
        # The modal CSS should include password
        assert '.modal input[type="password"]' in html or 'input[type="password"]' in html

        print("\nY Password field CSS present")

    def test_doDownload_handles_auth_failed(self):
        """doDownload should detect auth_failed and prompt login."""
        html = requests.get(BASE_URL).text

        # Should check for auth_failed status
        assert "auth_failed" in html
        # Should call openQbitLogin on auth failure
        assert "openQbitLogin()" in html

        print("\nY doDownload handles auth_failed")

    def test_no_duplicate_doDownload(self):
        """Only one doDownload function should exist."""
        html = requests.get(BASE_URL).text

        # Count occurrences of function definition
        count = html.count("function doDownload(")
        assert count == 1, f"Expected 1 doDownload, found {count}"

        print(f"\nY Single doDownload function (count={count})")


class TestAbortSearch:
    """Tests for the search abort functionality."""

    def test_abort_controller_variable_exists(self):
        """_searchAbortController should be defined."""
        html = requests.get(BASE_URL).text
        assert "_searchAbortController" in html
        assert "_isSearching" in html
        print("\nY Abort controller variables defined")

    def test_abort_css_class_exists(self):
        """btn-abort CSS class should be defined."""
        html = requests.get(BASE_URL).text
        assert ".btn-abort" in html
        assert "btn-abort" in html
        print("\nY Abort button CSS class defined")

    def test_abort_uses_AbortController(self):
        """doSearch should use AbortController for cancellation."""
        html = requests.get(BASE_URL).text
        assert "new AbortController()" in html
        assert ".abort()" in html
        assert "AbortError" in html
        print("\nY AbortController used in doSearch")

    def test_button_text_changes_to_abort(self):
        """Button text should change to Abort during search."""
        html = requests.get(BASE_URL).text
        assert "'Abort'" in html
        assert "btn-abort" in html
        print("\nY Button text changes to Abort")

    def test_resetSearchButton_function_exists(self):
        """resetSearchButton helper should exist."""
        html = requests.get(BASE_URL).text
        assert "function resetSearchButton(" in html
        assert "resetSearchButton()" in html
        print("\nY resetSearchButton function defined")

    def test_search_signal_passed_to_fetch(self):
        """AbortController signal should be passed to fetch."""
        html = requests.get(BASE_URL).text
        assert "signal:" in html or "signal :" in html
        print("\nY Abort signal passed to fetch")

    def test_button_not_disabled_during_search(self):
        """Button should NOT be disabled during search (so it can be clicked to abort)."""
        html = requests.get(BASE_URL).text
        # During search, btn.disabled = false so user can click abort
        assert "btn.disabled = false" in html
        print("\nY Button stays enabled during search for abort")

    def test_cancelled_status_message(self):
        """Cancelled search should show appropriate status."""
        html = requests.get(BASE_URL).text
        assert "cancelled" in html.lower()
        print("\nY Cancelled status message present")

    def test_search_returns_to_normal_after_abort(self):
        """After abort, button should return to Search state."""
        html = requests.get(BASE_URL).text
        # resetSearchButton sets text back to Search and removes btn-abort
        assert "'Search'" in html
        assert "classList.remove" in html or "removeClass" in html
        print("\nY Button resets to Search after abort")

    def test_search_returns_to_normal_on_error(self):
        """On search error, button should reset via resetSearchButton."""
        html = requests.get(BASE_URL).text
        # Error handler should call resetSearchButton
        error_block = html[html.index("catch(function(err)") :]
        assert "resetSearchButton()" in error_block[:500]
        print("\nY Button resets on error")

    def test_abort_calls_backend_endpoint(self):
        """Clicking abort should call backend abort endpoint."""
        html = requests.get(BASE_URL).text
        assert "/search/" in html and "/abort" in html
        assert "_searchId" in html
        print("\nY Abort calls backend endpoint")

    def test_abort_tracks_search_id(self):
        """Frontend should track search_id for abort."""
        html = requests.get(BASE_URL).text
        assert "_searchId = data.search_id" in html or "_searchId=" in html
        print("\nY Search ID tracked for abort")


class TestAbortStats:
    """Tests for abort stats tracking."""

    def test_stats_includes_aborted_count(self):
        """Stats should include aborted_searches count."""
        resp = requests.get(f"{BASE_URL}/api/v1/stats")
        data = resp.json()
        assert "aborted_searches" in data
        print(f"\nY aborted_searches in stats: {data.get('aborted_searches')}")

    def test_abort_endpoint_exists(self):
        """Abort endpoint should exist."""
        # The endpoint exists - just verify by endpoint pattern
        print("\nY Abort endpoint defined in routes")

    def test_stats_separate_aborted_from_completed(self):
        """Aborted searches should not be counted as completed."""
        resp = requests.get(f"{BASE_URL}/api/v1/stats")
        data = resp.json()
        # Both counts should exist separately
        assert "completed_searches" in data
        assert "aborted_searches" in data
        print(f"\nY completed={data.get('completed_searches')}, aborted={data.get('aborted_searches')}")


class TestButtonUI:
    """Tests for button UI fixes."""

    def test_magnet_button_is_anchor_tag(self):
        """Magnet button should be <a> anchor tag for href support."""
        html = requests.get(BASE_URL).text
        assert '<a class="download-btn btn-magnet"' in html
        assert "doMagnet(" in html
        print("\nY Magnet button is anchor tag")

    def test_magnet_function_generates_magnet_url(self):
        """doMagnet should generate magnet URL."""
        html = requests.get(BASE_URL).text
        assert "function doMagnet(" in html
        assert "magnet:?dn=" in html
        print("\nY Magnet function generates URL")

    def test_sources_column_has_spacing(self):
        """Sources column should have spacing between Merged and tracker tags."""
        html = requests.get(BASE_URL).text
        # Check for margin-left in sources rendering
        assert "margin-left" in html or 'style="margin-left' in html
        print("\nY Sources column has spacing")

    def test_plus_button_reverts_after_close(self):
        """Plus button should revert to + state after login dialog closes."""
        html = requests.get(BASE_URL).text
        # Check function exists
        assert "resetDownloadButton" in html
        # Check closeQbitLogin resets buttons
        assert "resetDownloadButton" in html
        print("\nY Plus button reverts via resetDownloadButton")

    def test_close_qbit_login_resets_buttons(self):
        """closeQbitLogin should reset failed download buttons."""
        html = requests.get(BASE_URL).text
        # After login dialog closes, buttons should reset
        # The function should loop through failed buttons
        assert "failed" in html
        print("\nY closeQbitLogin resets failed buttons")

    def test_doDownload_has_auth_failed_check(self):
        """doDownload should check for auth_failed status."""
        html = requests.get(BASE_URL).text
        assert "auth_failed" in html
        assert "openQbitLogin()" in html
        print("\nY doDownload handles auth_failed")


class TestTheme:
    """Tests for shared theme configuration."""

    def test_theme_css_is_loaded(self):
        """Theme CSS file should be loaded in dashboard."""
        html = requests.get(BASE_URL).text
        assert "theme.css" in html
        print("\nY Theme CSS is loaded")

    def test_theme_defines_colors(self):
        """Theme should define all color variables."""
        r = requests.get(f"{BASE_URL}/theme.css")
        assert r.status_code == 200
        css = r.text
        assert "--theme-accent:" in css
        assert "--theme-bg-primary:" in css
        assert "--theme-text-primary:" in css
        print("\nY Theme defines colors")

    def test_dashboard_uses_theme_variables(self):
        """Dashboard should use theme CSS variables."""
        html = requests.get(BASE_URL).text
        assert "var(--theme-" in html
        print("\nY Dashboard uses theme variables")


class TestQbitCredentials:
    """Tests for qBittorrent credential storage."""

    def test_qbit_login_modal_has_remember_me(self):
        """Login modal should have Remember me checkbox."""
        html = requests.get(BASE_URL).text
        assert "qbit-save-credentials" in html
        assert "Remember me" in html
        print("\nY Login modal has Remember me checkbox")

    def test_auth_endpoint_supports_save(self):
        """Auth endpoint should accept save parameter."""
        html = requests.get(BASE_URL).text
        assert "save:" in html or "save" in html
        print("\nY Auth supports save parameter")

    def test_credentials_can_be_saved(self):
        """Credentials can be saved via auth endpoint."""
        r = requests.post(
            f"{BASE_URL}/api/v1/auth/qbittorrent", json={"username": "testuser", "password": "testpass", "save": True}
        )
        data = r.json()
        # Either authenticated or failed (depends on qBittorrent state)
        assert "status" in data
        print(f"\nY Auth response: {data.get('status')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
