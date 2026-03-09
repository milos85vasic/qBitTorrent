#!/usr/bin/env python3
"""
Comprehensive test for ALL search providers
Tests both search functionality and download capability
"""

import os
import sys
import time
import subprocess

# Test configuration
TEST_QUERY = "ubuntu"
CONTAINER_NAME = "qbittorrent"
PLUGINS = [
    # Official plugins (should work with WebUI)
    ("eztv", "EZTV", True),
    ("jackett", "Jackett", True),
    ("limetorrents", "LimeTorrents", True),
    ("piratebay", "The Pirate Bay", True),
    ("solidtorrents", "Solid Torrents", True),
    ("torlock", "TorLock", True),
    ("torrentproject", "TorrentProject", True),
    ("torrentscsv", "torrents-csv", True),
    # Russian plugins (may need special handling)
    ("rutor", "Rutor", True),
    ("rutracker", "RuTracker", False),  # Requires auth
    ("kinozal", "Kinozal", False),      # Requires auth
    ("nnmclub", "NoNaMe-Club", False),  # Requires auth
]


def test_search_in_container(plugin_name):
    """Test search via nova2.py in container."""
    try:
        cmd = [
            "podman", "exec", "-u", "abc", CONTAINER_NAME,
            "python3", "/config/qBittorrent/nova3/nova2.py",
            plugin_name, "all", TEST_QUERY
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return False, f"Exit code {result.returncode}: {result.stderr[:100]}"
        
        # Parse results
        lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
        if not lines:
            return False, "No results returned"
        
        # Check first result format
        parts = lines[0].split('|')
        if len(parts) < 6:
            return False, f"Invalid format: {lines[0][:80]}"
        
        return True, f"{len(lines)} results"
        
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)[:100]


def test_download_in_container(plugin_name):
    """Test download capability via nova2dl.py in container."""
    # Get a test URL first
    try:
        search_cmd = [
            "podman", "exec", "-u", "abc", CONTAINER_NAME,
            "python3", "/config/qBittorrent/nova3/nova2.py",
            plugin_name, "all", "ubuntu"
        ]
        
        search_result = subprocess.run(
            search_cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if search_result.returncode != 0 or not search_result.stdout.strip():
            return None, "No search results to test download"
        
        # Extract URL from first result
        first_line = search_result.stdout.strip().split('\n')[0]
        parts = first_line.split('|')
        if not parts:
            return None, "Could not parse search result"
        
        test_url = parts[0]
        
        # Test download
        download_cmd = [
            "podman", "exec", "-u", "abc", CONTAINER_NAME,
            "python3", "/config/qBittorrent/nova3/nova2dl.py",
            plugin_name, test_url
        ]
        
        download_result = subprocess.run(
            download_cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if download_result.returncode != 0:
            return False, f"Download failed: {download_result.stderr[:100]}"
        
        # Parse output: "filepath url"
        output = download_result.stdout.strip()
        if not output or ' ' not in output:
            return False, "Invalid download output format"
        
        torrent_path = output.split(' ')[0]
        
        # Verify file exists in container
        check_cmd = [
            "podman", "exec", CONTAINER_NAME,
            "test", "-f", torrent_path
        ]
        
        check_result = subprocess.run(check_cmd, capture_output=True)
        
        if check_result.returncode == 0:
            # Clean up
            subprocess.run(
                ["podman", "exec", CONTAINER_NAME, "rm", "-f", torrent_path],
                capture_output=True
            )
            return True, "Download successful"
        else:
            return False, "Downloaded file not found"
            
    except subprocess.TimeoutExpired:
        return False, "Download timeout"
    except Exception as e:
        return False, str(e)[:100]


def main():
    print("="*80)
    print("COMPREHENSIVE SEARCH PROVIDER TEST")
    print("="*80)
    print(f"\nTesting {len(PLUGINS)} search providers...")
    print(f"Test query: '{TEST_QUERY}'")
    print("")
    
    results = {}
    
    for plugin_name, display_name, should_work in PLUGINS:
        print(f"\n{'='*80}")
        print(f"Testing: {display_name} ({plugin_name})")
        print(f"{'='*80}")
        
        results[plugin_name] = {
            'name': display_name,
            'search': None,
            'download': None
        }
        
        # Test Search
        print("\n  [1/2] Testing SEARCH...")
        search_ok, search_msg = test_search_in_container(plugin_name)
        results[plugin_name]['search'] = (search_ok, search_msg)
        
        if search_ok:
            print(f"      ✓ Search: {search_msg}")
        else:
            print(f"      ✗ Search: {search_msg}")
        
        # Test Download
        print("\n  [2/2] Testing DOWNLOAD...")
        download_ok, download_msg = test_download_in_container(plugin_name)
        results[plugin_name]['download'] = (download_ok, download_msg)
        
        if download_ok is True:
            print(f"      ✓ Download: {download_msg}")
        elif download_ok is False:
            print(f"      ✗ Download: {download_msg}")
        else:
            print(f"      ⚠ Download: {download_msg}")
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    print("\n{:<20} {:<20} {:<20} {:<20}".format(
        "Plugin", "Search", "Download", "Status"
    ))
    print("-"*80)
    
    total_pass = 0
    total_fail = 0
    
    for plugin_name, data in results.items():
        search_ok, _ = data['search']
        download_ok, _ = data['download']
        
        search_status = "✓" if search_ok else "✗"
        
        if download_ok is True:
            download_status = "✓"
            overall = "✓ WORKING"
            total_pass += 1
        elif download_ok is False:
            download_status = "✗"
            overall = "✗ FAILED"
            total_fail += 1
        else:
            download_status = "⚠"
            overall = "⚠ PARTIAL"
        
        print("{:<20} {:<20} {:<20} {:<20}".format(
            data['name'][:19],
            search_status,
            download_status,
            overall
        ))
    
    print("-"*80)
    print(f"\nTotal: {total_pass} fully working, {total_fail} failed")
    
    print("\n" + "="*80)
    if total_fail == 0:
        print("✓ ALL PROVIDERS WORKING!")
        print("="*80)
        return 0
    else:
        print("✗ SOME PROVIDERS NEED ATTENTION")
        print("="*80)
        return 1


if __name__ == "__main__":
    sys.exit(main())
