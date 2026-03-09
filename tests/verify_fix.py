#!/usr/bin/env python3
"""Simple test to verify the download_torrent fix."""

import os
import sys
import tempfile
from io import BytesIO, StringIO
from unittest.mock import MagicMock, Mock, patch

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "plugins"))

import novaprinter
from rutracker import RuTracker

print("=" * 70)
print("Testing download_torrent fix")
print("=" * 70)

# Create mock opener
mock_opener = MagicMock()
mock_response = MagicMock()
mock_response.getcode.return_value = 200
mock_response.read.return_value = b"d8:announce31:http://example.com/announce"
mock_response.info.return_value.get.return_value = None
mock_response.__enter__ = Mock(return_value=mock_response)
mock_response.__exit__ = Mock(return_value=False)
mock_opener.open.return_value = mock_response

# Create plugin instance without login
plugin = RuTracker.__new__(RuTracker)
plugin.cj = MagicMock()
plugin.opener = mock_opener

test_url = "https://rutracker.org/forum/dl.php?t=12345"

print("\n1. Testing output format...")
captured = StringIO()
with patch("sys.stdout", captured):
    plugin.download_torrent(test_url)

output = captured.getvalue()
print(f"   Output: {output.strip()}")

parts = output.strip().split(" ")
if len(parts) == 2:
    filepath, url = parts
    print(f"   ✓ Format is correct: filepath url")
    print(f"   ✓ File path: {filepath}")
    print(f"   ✓ URL: {url}")
else:
    print(f"   ✗ Format is incorrect, expected 2 parts, got {len(parts)}")
    sys.exit(1)

print("\n2. Testing file creation...")
if os.path.exists(filepath):
    print(f"   ✓ Torrent file exists")

    with open(filepath, "rb") as f:
        content = f.read()

    if content == b"d8:announce31:http://example.com/announce":
        print(f"   ✓ File content is correct")
    else:
        print(f"   ✗ File content mismatch")
        sys.exit(1)

    # Clean up
    os.unlink(filepath)
else:
    print(f"   ✗ Torrent file not found")
    sys.exit(1)

print("\n3. Testing file flushing...")
with patch("tempfile.NamedTemporaryFile") as mock_tempfile:
    mock_file = MagicMock()
    mock_file.name = "/tmp/test_flush.torrent"
    mock_file.write = Mock()
    mock_file.flush = Mock()
    mock_file.fileno = Mock(return_value=3)
    mock_file.__enter__ = Mock(return_value=mock_file)
    mock_file.__exit__ = Mock(return_value=False)
    mock_tempfile.return_value = mock_file

    with patch("sys.stdout"):
        with patch("os.fsync") as mock_fsync:
            plugin.download_torrent(test_url)

            if mock_file.flush.called:
                print(f"   ✓ File flush was called")
            else:
                print(f"   ✗ File flush was not called")
                sys.exit(1)

            if mock_fsync.called:
                print(f"   ✓ os.fsync was called")
            else:
                print(f"   ✗ os.fsync was not called")
                sys.exit(1)

print("\n4. Testing stdout flushing...")
with patch("sys.stdout") as mock_stdout:
    plugin.download_torrent(test_url)

    if mock_stdout.flush.called:
        print(f"   ✓ stdout.flush was called")
    else:
        print(f"   ✗ stdout.flush was not called")
        sys.exit(1)

print("\n" + "=" * 70)
print("ALL TESTS PASSED!")
print("=" * 70)
print("\nThe fix successfully:")
print("  1. Creates a torrent file")
print("  2. Flushes the file to disk")
print("  3. Syncs the file to ensure it's written")
print("  4. Prints the correct output format (filepath url)")
print("  5. Flushes stdout to ensure output is immediately available")
print("\nThis should fix the issue where downloads from RuTracker plugin")
print("didn't start in qBittorrent.")
