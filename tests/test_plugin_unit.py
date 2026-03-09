#!/usr/bin/env python3
"""Unit tests for RuTracker plugin."""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch
from io import BytesIO, StringIO

tests_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, tests_dir)

plugins_dir = os.path.join(os.path.dirname(tests_dir), "plugins")
sys.path.insert(0, plugins_dir)

import novaprinter

from rutracker import RuTracker


class TestRuTrackerPlugin(unittest.TestCase):
    """Unit tests for RuTracker plugin functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_opener = MagicMock()
        self.mock_response = MagicMock()
        self.mock_response.getcode.return_value = 200
        self.mock_response.read.return_value = (
            b"d8:announce31:http://example.com/announce"
        )
        self.mock_response.info.return_value.get.return_value = None
        self.mock_response.__enter__ = Mock(return_value=self.mock_response)
        self.mock_response.__exit__ = Mock(return_value=False)

    def _create_mock_plugin(self):
        """Create a mock plugin instance without calling __init__."""
        plugin = RuTracker.__new__(RuTracker)
        plugin.cj = MagicMock()
        plugin.opener = self.mock_opener
        plugin.url = "https://rutracker.org"
        return plugin

    def test_download_torrent_flushes_file(self):
        """Test that download_torrent flushes and syncs the file."""
        plugin = self._create_mock_plugin()
        test_url = "https://rutracker.org/forum/dl.php?t=12345"

        with patch("tempfile.NamedTemporaryFile") as mock_tempfile:
            mock_file = MagicMock()
            mock_file.name = "/tmp/test123.torrent"
            mock_file.write = Mock()
            mock_file.flush = Mock()
            mock_file.fileno = Mock(return_value=3)
            mock_file.__enter__ = Mock(return_value=mock_file)
            mock_file.__exit__ = Mock(return_value=False)
            mock_tempfile.return_value = mock_file

            with patch("sys.stdout") as mock_stdout:
                with patch("os.fsync") as mock_fsync:
                    plugin.download_torrent(test_url)

                    mock_file.write.assert_called_once()
                    mock_file.flush.assert_called_once()
                    mock_fsync.assert_called_once_with(3)

    def test_download_torrent_flushes_stdout(self):
        """Test that download_torrent flushes stdout."""
        plugin = self._create_mock_plugin()
        test_url = "https://rutracker.org/forum/dl.php?t=12345"

        with patch("sys.stdout") as mock_stdout:
            plugin.download_torrent(test_url)
            mock_stdout.flush.assert_called()

    def test_download_torrent_with_cookies(self):
        """Test that download_torrent uses cookies from login."""
        plugin = self._create_mock_plugin()
        test_url = "https://rutracker.org/forum/dl.php?t=12345"

        plugin.download_torrent(test_url)

        self.assertTrue(self.mock_opener.open.called)

    def test_search_builds_correct_result(self):
        """Test that search builds correct result dict."""
        plugin = self._create_mock_plugin()

        torrent_data = {
            "id": "12345",
            "title": "Test Torrent",
            "size": "1073741824",
            "seeds": "10",
            "leech": "5",
            "pub_date": "1234567890",
        }

        result = plugin._RuTracker__build_result(torrent_data)

        self.assertEqual(result["id"], "12345")
        self.assertEqual(result["name"], "Test Torrent")
        self.assertEqual(result["size"], "1073741824")
        self.assertEqual(result["seeds"], "10")
        self.assertEqual(result["leech"], "5")
        self.assertIn("t=12345", result["link"])
        self.assertIn("t=12345", result["desc_link"])


class TestDownloadTorrentOutput(unittest.TestCase):
    """Test the output format of download_torrent."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_opener = MagicMock()
        self.mock_response = MagicMock()
        self.mock_response.getcode.return_value = 200
        self.mock_response.read.return_value = (
            b"d8:announce31:http://example.com/announce"
        )
        self.mock_response.info.return_value.get.return_value = None
        self.mock_response.__enter__ = Mock(return_value=self.mock_response)
        self.mock_response.__exit__ = Mock(return_value=False)

    def _create_mock_plugin(self):
        """Create a mock plugin instance without calling __init__."""
        plugin = RuTracker.__new__(RuTracker)
        plugin.cj = MagicMock()
        plugin.opener = self.mock_opener
        plugin.url = "https://rutracker.org"
        return plugin

    def test_output_format_is_correct(self):
        """Test that output is 'filepath url' format."""
        plugin = self._create_mock_plugin()
        test_url = "https://rutracker.org/forum/dl.php?t=12345"

        captured_output = StringIO()

        with patch("sys.stdout", captured_output):
            plugin.download_torrent(test_url)

        output = captured_output.getvalue()
        self.assertIn(test_url, output)
        self.assertIn(".torrent", output)

        parts = output.strip().split(" ")
        self.assertEqual(len(parts), 2)
        self.assertTrue(parts[0].endswith(".torrent"))
        self.assertEqual(parts[1], test_url)

    def test_file_is_created_and_valid(self):
        """Test that torrent file is created and contains valid data."""
        plugin = self._create_mock_plugin()
        test_url = "https://rutracker.org/forum/dl.php?t=12345"

        captured_output = StringIO()

        with patch("sys.stdout", captured_output):
            plugin.download_torrent(test_url)

        output = captured_output.getvalue()
        parts = output.strip().split(" ")
        filepath = parts[0]

        try:
            self.assertTrue(os.path.exists(filepath), "Torrent file should exist")

            with open(filepath, "rb") as f:
                content = f.read()

            self.assertEqual(content, b"d8:announce31:http://example.com/announce")
            self.assertTrue(content.startswith(b"d"))
        finally:
            try:
                os.unlink(filepath)
            except:
                pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
