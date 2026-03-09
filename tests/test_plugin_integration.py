#!/usr/bin/env python3
"""Integration tests for RuTracker plugin with real RuTracker connection."""

import os
import sys
import unittest
import tempfile

tests_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, tests_dir)

plugins_dir = os.path.join(os.path.dirname(tests_dir), "plugins")
sys.path.insert(0, plugins_dir)

import novaprinter

from rutracker import RuTracker, CONFIG


def has_credentials():
    """Check if RuTracker credentials are configured."""
    username = CONFIG.username
    password = CONFIG.password
    return (
        username
        and username not in ["YOUR_USERNAME_HERE", "your_username_here"]
        and password
        and password not in ["YOUR_PASSWORD_HERE", "your_password_here"]
    )


@unittest.skipIf(not has_credentials(), "RuTracker credentials not configured")
class TestRuTrackerIntegration(unittest.TestCase):
    """Integration tests with real RuTracker connection."""

    @classmethod
    def setUpClass(cls):
        """Set up test class with real RuTracker connection."""
        try:
            cls.plugin = RuTracker()
            cls.has_connection = True
        except Exception as e:
            cls.has_connection = False
            cls.skip_reason = str(e)

    def setUp(self):
        """Skip tests if connection failed."""
        if not self.has_connection:
            self.skipTest(
                f"Failed to connect to RuTracker: {getattr(self, 'skip_reason', 'Unknown error')}"
            )

    def test_login_successful(self):
        """Test that login to RuTracker is successful."""
        self.assertIsNotNone(self.plugin.cj)
        cookie_names = [cookie.name for cookie in self.plugin.cj]
        self.assertIn("bb_session", cookie_names)

    def test_search_returns_results(self):
        """Test that search returns results."""
        self.plugin.results = {}
        self.plugin.search("ubuntu")

        self.assertIsInstance(self.plugin.results, dict)
        self.assertGreater(len(self.plugin.results), 0)

    def test_search_result_structure(self):
        """Test that search results have correct structure."""
        self.plugin.results = {}
        self.plugin.search("ubuntu")

        if self.plugin.results:
            first_result = list(self.plugin.results.values())[0]

            required_keys = [
                "id",
                "link",
                "name",
                "size",
                "seeds",
                "leech",
                "engine_url",
                "desc_link",
                "pub_date",
            ]
            for key in required_keys:
                self.assertIn(key, first_result, f"Missing key: {key}")

            self.assertTrue(first_result["link"].startswith("http"))
            self.assertTrue(first_result["desc_link"].startswith("http"))

    def test_download_torrent_creates_file(self):
        """Test that download_torrent creates a valid torrent file."""
        self.plugin.results = {}
        self.plugin.search("ubuntu")

        if not self.plugin.results:
            self.skipTest("No search results found")

        first_result = list(self.plugin.results.values())[0]
        download_url = first_result["link"]

        output_lines = []
        original_stdout = sys.stdout

        class CaptureOutput:
            def __init__(self):
                self.lines = []

            def write(self, text):
                self.lines.append(text)

            def flush(self):
                pass

        captured = CaptureOutput()
        sys.stdout = captured

        try:
            self.plugin.download_torrent(download_url)
        finally:
            sys.stdout = original_stdout

        output = "".join(captured.lines).strip()
        parts = output.split(" ")

        self.assertEqual(len(parts), 2, f"Output format incorrect: {output}")

        filepath = parts[0]
        url = parts[1]

        self.assertTrue(
            filepath.endswith(".torrent"),
            f"File path should end with .torrent: {filepath}",
        )
        self.assertEqual(url, download_url)

        self.assertTrue(
            os.path.exists(filepath), f"Torrent file not created: {filepath}"
        )

        try:
            with open(filepath, "rb") as f:
                content = f.read()

            self.assertGreater(len(content), 0)
            self.assertIn(b"d8:", content[:10])

        finally:
            try:
                os.unlink(filepath)
            except:
                pass

    def test_download_torrent_valid_bencode(self):
        """Test that downloaded torrent has valid bencode structure."""
        self.plugin.results = {}
        self.plugin.search("ubuntu")

        if not self.plugin.results:
            self.skipTest("No search results found")

        first_result = list(self.plugin.results.values())[0]
        download_url = first_result["link"]

        captured = []
        original_stdout = sys.stdout

        class CaptureOutput:
            def write(self, text):
                captured.append(text)

            def flush(self):
                pass

        sys.stdout = CaptureOutput()

        try:
            self.plugin.download_torrent(download_url)
        finally:
            sys.stdout = original_stdout

        output = "".join(captured).strip()
        filepath = output.split(" ")[0]

        try:
            with open(filepath, "rb") as f:
                content = f.read()

            self.assertTrue(content.startswith(b"d"))
            self.assertIn(b":announce", content)

        finally:
            try:
                os.unlink(filepath)
            except:
                pass

    def test_multiple_downloads(self):
        """Test downloading multiple torrents in sequence."""
        self.plugin.results = {}
        self.plugin.search("ubuntu")

        if len(self.plugin.results) < 2:
            self.skipTest("Not enough search results")

        downloaded_files = []

        try:
            for i, result in enumerate(list(self.plugin.results.values())[:2]):
                download_url = result["link"]

                captured = []
                original_stdout = sys.stdout

                class CaptureOutput:
                    def write(self, text):
                        captured.append(text)

                    def flush(self):
                        pass

                sys.stdout = CaptureOutput()

                try:
                    self.plugin.download_torrent(download_url)
                finally:
                    sys.stdout = original_stdout

                output = "".join(captured).strip()
                filepath = output.split(" ")[0]

                self.assertTrue(os.path.exists(filepath))
                downloaded_files.append(filepath)

        finally:
            for filepath in downloaded_files:
                try:
                    os.unlink(filepath)
                except:
                    pass


if __name__ == "__main__":
    if not has_credentials():
        print("Skipping integration tests - RuTracker credentials not configured")
        print("Set RUTRACKER_USERNAME and RUTRACKER_PASSWORD environment variables")
        print("or create ~/.qbit.env file with credentials")
        sys.exit(0)

    unittest.main(verbosity=2)
