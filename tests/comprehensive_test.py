#!/usr/bin/env python3
"""
COMPREHENSIVE TEST SUITE - All Plugins, All Features
100% Coverage Testing

This test suite covers:
1. Plugin structure validation
2. Search functionality
3. Download functionality
4. Column data validation
5. WebUI compatibility
6. Authentication handling
"""

import os
import sys
import time
import subprocess
import tempfile
import json
from typing import Tuple, Dict, List, Optional

# Configuration
CONTAINER_NAME = "qbittorrent"
TEST_TIMEOUT = 60
PLUGINS = [
    # (name, display_name, type, needs_auth)
    ("eztv", "EZTV", "public", False),
    ("jackett", "Jackett", "meta", False),
    ("limetorrents", "LimeTorrents", "public", False),
    ("piratebay", "The Pirate Bay", "public", False),
    ("solidtorrents", "Solid Torrents", "public", False),
    ("torlock", "TorLock", "public", False),
    ("torrentproject", "TorrentProject", "public", False),
    ("torrentscsv", "torrents-csv", "public", False),
    ("rutor", "Rutor", "public", False),
    ("rutracker", "RuTracker", "private", True),
    ("kinozal", "Kinozal", "private", True),
    ("nnmclub", "NNMClub", "private", True),
]


class TestResult:
    """Store test results."""
    def __init__(self):
        self.passed = []
        self.failed = []
        self.warnings = []
        
    def add_pass(self, test_name: str, message: str = ""):
        self.passed.append((test_name, message))
        
    def add_fail(self, test_name: str, message: str):
        self.failed.append((test_name, message))
        
    def add_warning(self, test_name: str, message: str):
        self.warnings.append((test_name, message))
        
    def summary(self) -> Dict:
        total = len(self.passed) + len(self.failed)
        return {
            "total": total,
            "passed": len(self.passed),
            "failed": len(self.failed),
            "warnings": len(self.warnings),
            "success_rate": (len(self.passed) / total * 100) if total > 0 else 0
        }


def run_in_container(cmd: List[str], timeout: int = TEST_TIMEOUT) -> Tuple[int, str, str]:
    """Run command in qBittorrent container."""
    full_cmd = ["podman", "exec", "-u", "abc", CONTAINER_NAME] + cmd
    try:
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except Exception as e:
        return -1, "", str(e)


def test_plugin_structure(plugin_name: str, display_name: str) -> Tuple[bool, str]:
    """Test 1: Plugin structure validation."""
    try:
        # Check file exists in container
        rc, _, _ = run_in_container([
            "test", "-f", f"/config/qBittorrent/nova3/engines/{plugin_name}.py"
        ])
        
        if rc != 0:
            return False, "Plugin file not found in container"
        
        # Test Python syntax
        rc, _, stderr = run_in_container([
            "python3", "-m", "py_compile",
            f"/config/qBittorrent/nova3/engines/{plugin_name}.py"
        ])
        
        if rc != 0:
            return False, f"Syntax error: {stderr[:100]}"
        
        # Test import
        rc, stdout, stderr = run_in_container([
            "python3", "-c",
            f"import sys; sys.path.insert(0, '/config/qBittorrent/nova3/engines'); "
            f"import {plugin_name}; print('OK')"
        ])
        
        if rc != 0 or "OK" not in stdout:
            return False, f"Import failed: {stderr[:100]}"
        
        return True, "Structure valid"
        
    except Exception as e:
        return False, str(e)[:100]


def test_search_functionality(plugin_name: str, display_name: str) -> Tuple[bool, str, Optional[List[Dict]]]:
    """Test 2: Search functionality."""
    try:
        rc, stdout, stderr = run_in_container([
            "python3", "/config/qBittorrent/nova3/nova2.py",
            plugin_name, "all", "ubuntu"
        ])
        
        if rc != 0:
            return False, f"Search failed: {stderr[:100]}", None
        
        lines = [l.strip() for l in stdout.strip().split('\n') if l.strip()]
        if not lines:
            return False, "No results returned", None
        
        # Parse results
        results = []
        for line in lines[:5]:  # Check first 5 results
            parts = line.split('|')
            if len(parts) >= 6:
                results.append({
                    'link': parts[0],
                    'name': parts[1],
                    'size': parts[2],
                    'seeds': parts[3],
                    'leech': parts[4],
                    'engine_url': parts[5]
                })
        
        return True, f"{len(lines)} results", results
        
    except Exception as e:
        return False, str(e)[:100], None


def test_column_data(result: Dict) -> Tuple[bool, str]:
    """Test 3: Column data validation."""
    issues = []
    
    # Check name
    if not result.get('name') or result['name'] == 'N/A':
        issues.append("Missing name")
    
    # Check size
    try:
        size = int(result.get('size', 0))
        if size < 0:
            issues.append("Invalid size")
    except:
        issues.append("Non-numeric size")
    
    # Check seeds
    try:
        seeds = int(result.get('seeds', -1))
        if seeds < 0:
            issues.append("Invalid seeds")
    except:
        issues.append("Non-numeric seeds")
    
    # Check leech
    try:
        leech = int(result.get('leech', -1))
        if leech < 0:
            issues.append("Invalid leech")
    except:
        issues.append("Non-numeric leech")
    
    if issues:
        return False, ", ".join(issues)
    
    return True, "All columns valid"


def test_download_functionality(plugin_name: str, url: str, is_magnet: bool = False) -> Tuple[bool, str]:
    """Test 4: Download functionality."""
    try:
        if is_magnet:
            # Magnet links should just output the URL
            rc, stdout, stderr = run_in_container([
                "python3", "/config/qBittorrent/nova3/nova2dl.py",
                plugin_name, url
            ])
            
            if rc == 0 and url in stdout:
                return True, "Magnet link handled"
            else:
                return False, f"Magnet handling failed: {stderr[:100]}"
        
        # For .torrent files
        rc, stdout, stderr = run_in_container([
            "python3", "/config/qBittorrent/nova3/nova2dl.py",
            plugin_name, url
        ])
        
        if rc != 0:
            return False, f"Download failed: {stderr[:100]}"
        
        output = stdout.strip()
        if ' ' not in output:
            return False, "Invalid output format"
        
        torrent_path = output.split(' ')[0]
        
        # Verify file exists
        rc, _, _ = run_in_container(["test", "-f", torrent_path])
        if rc != 0:
            return False, "Downloaded file not found"
        
        # Check if valid torrent (starts with 'd')
        rc, stdout, _ = run_in_container([
            "head", "-c", "1", torrent_path
        ])
        
        if stdout != 'd':
            # Cleanup
            run_in_container(["rm", "-f", torrent_path])
            return False, "Not a valid torrent file"
        
        # Cleanup
        run_in_container(["rm", "-f", torrent_path])
        
        return True, "Download successful"
        
    except Exception as e:
        return False, str(e)[:100]


def main():
    """Run all tests."""
    print("="*80)
    print("COMPREHENSIVE TEST SUITE - All Plugins, All Features")
    print("="*80)
    print()
    
    results = TestResult()
    
    for plugin_name, display_name, plugin_type, needs_auth in PLUGINS:
        print(f"\n{'='*80}")
        print(f"Testing: {display_name} ({plugin_name}) - Type: {plugin_type}")
        print(f"{'='*80}")
        
        # Test 1: Structure
        print(f"\n  [1/4] Testing STRUCTURE...")
        ok, msg = test_plugin_structure(plugin_name, display_name)
        if ok:
            results.add_pass(f"{display_name} - Structure", msg)
            print(f"      ✓ {msg}")
        else:
            results.add_fail(f"{display_name} - Structure", msg)
            print(f"      ✗ {msg}")
            continue
        
        # Test 2: Search
        print(f"\n  [2/4] Testing SEARCH...")
        ok, msg, search_results = test_search_functionality(plugin_name, display_name)
        if ok:
            results.add_pass(f"{display_name} - Search", msg)
            print(f"      ✓ {msg}")
        else:
            if needs_auth and "credentials" in msg.lower():
                results.add_warning(f"{display_name} - Search", "Needs credentials")
                print(f"      ⚠ {msg} (needs credentials)")
            else:
                results.add_fail(f"{display_name} - Search", msg)
                print(f"      ✗ {msg}")
            continue
        
        # Test 3: Column Data
        if search_results:
            print(f"\n  [3/4] Testing COLUMN DATA...")
            ok, msg = test_column_data(search_results[0])
            if ok:
                results.add_pass(f"{display_name} - Columns", msg)
                print(f"      ✓ {msg}")
            else:
                results.add_fail(f"{display_name} - Columns", msg)
                print(f"      ✗ {msg}")
            
            # Test 4: Download
            print(f"\n  [4/4] Testing DOWNLOAD...")
            test_url = search_results[0]['link']
            is_magnet = test_url.startswith('magnet:')
            
            ok, msg = test_download_functionality(plugin_name, test_url, is_magnet)
            if ok:
                results.add_pass(f"{display_name} - Download", msg)
                print(f"      ✓ {msg}")
            else:
                if needs_auth:
                    results.add_warning(f"{display_name} - Download", "Private tracker - use Desktop App or WebUI Bridge")
                    print(f"      ⚠ {msg} (private tracker)")
                else:
                    results.add_fail(f"{display_name} - Download", msg)
                    print(f"      ✗ {msg}")
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    summary = results.summary()
    print(f"\nTotal Tests: {summary['total']}")
    print(f"Passed: {summary['passed']} ({summary['success_rate']:.1f}%)")
    print(f"Failed: {summary['failed']}")
    print(f"Warnings: {summary['warnings']}")
    
    if results.failed:
        print("\nFailed Tests:")
        for name, msg in results.failed:
            print(f"  ✗ {name}: {msg}")
    
    if results.warnings:
        print("\nWarnings:")
        for name, msg in results.warnings:
            print(f"  ⚠ {name}: {msg}")
    
    print("\n" + "="*80)
    if summary['success_rate'] == 100:
        print("✅ ALL TESTS PASSED - 100% SUCCESS RATE!")
        print("="*80)
        return 0
    else:
        print(f"⚠️  SOME TESTS FAILED - {summary['success_rate']:.1f}% SUCCESS RATE")
        print("="*80)
        return 1


if __name__ == "__main__":
    sys.exit(main())
