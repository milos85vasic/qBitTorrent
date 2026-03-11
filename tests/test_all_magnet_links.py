#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive Plugin Validation Test
Tests all plugins to ensure they return magnet links for WebUI compatibility
"""

import os
import sys
import re
from pathlib import Path

MAGNET_REGEX = re.compile(r"^magnet:\?xt=urn:btih:[a-fA-F0-9]{40}", re.I)

PLUGINS_DIR = Path(__file__).parent.parent / "plugins"
sys.path.insert(0, str(PLUGINS_DIR.parent))

RESULTS = {"passed": 0, "failed": 0, "warnings": 0, "details": []}


def log_result(plugin_name: str, test_name: str, status: str, message: str = ""):
    """Log test result."""
    RESULTS[status] += 1
    symbol = "✅" if status == "passed" else "❌" if status == "failed" else "⚠️"
    entry = {
        "plugin": plugin_name,
        "test": test_name,
        "status": status,
        "message": message,
    }
    RESULTS["details"].append(entry)
    print(
        f"{symbol} [{plugin_name}] {test_name}: {status.upper()}{f' - {message}' if message else ''}"
    )


def check_plugin_file(plugin_path: Path) -> dict:
    """Check a plugin file for magnet link support."""
    plugin_name = plugin_path.stem
    results = {"name": plugin_name, "checks": []}

    try:
        content = plugin_path.read_text()

        if plugin_name in [
            "novaprinter",
            "nova2",
            "helpers",
            "socks",
            "download_proxy",
        ]:
            return results

        has_magnet_in_search = False
        has_download_torrent = "def download_torrent" in content

        magnet_patterns = [
            r"return.*magnet:",
            r'["\']link["\'].*magnet:',
            r"MagnetUri",
            r"res\[.link.\].*magnet",
            r"build_magnet_link",
            r"fetch_magnet",
        ]

        for pattern in magnet_patterns:
            if re.search(pattern, content, re.I):
                has_magnet_in_search = True
                break

        if has_magnet_in_search:
            log_result(plugin_name, "Magnet in search", "passed")
        else:
            log_result(
                plugin_name,
                "Magnet in search",
                "failed",
                "No magnet link generation detected",
            )

        if has_download_torrent:
            if "magnet:" in content and "print" in content:
                log_result(plugin_name, "download_torrent handles magnet", "passed")
            else:
                log_result(
                    plugin_name,
                    "download_torrent handles magnet",
                    "warning",
                    "May not handle magnet links",
                )

        results["checks"] = [
            {"test": "magnet_in_search", "passed": has_magnet_in_search},
            {"test": "download_torrent_exists", "passed": has_download_torrent},
        ]

    except Exception as e:
        log_result(plugin_name, "File check", "failed", str(e))
        results["error"] = str(e)

    return results


def test_plugin_structure(plugin_path: Path) -> bool:
    """Test that plugin has required structure."""
    plugin_name = plugin_path.stem

    if plugin_name in ["novaprinter", "nova2", "helpers", "socks", "download_proxy"]:
        return True

    try:
        content = plugin_path.read_text()

        required = [
            (r"class\s+\w+:", "class definition"),
            (r"def\s+search\s*\(", "search method"),
            (r'name\s*=\s*["\']', "name attribute"),
            (r'url\s*=\s*["\']', "url attribute"),
        ]

        all_passed = True
        for pattern, desc in required:
            if not re.search(pattern, content):
                log_result(plugin_name, f"Structure: {desc}", "failed", "Missing")
                all_passed = False

        return all_passed

    except Exception as e:
        log_result(plugin_name, "Structure check", "failed", str(e))
        return False


def run_all_checks():
    """Run all plugin checks."""
    print("=" * 80)
    print("COMPREHENSIVE PLUGIN VALIDATION TEST")
    print("=" * 80)
    print()

    plugin_files = sorted(PLUGINS_DIR.glob("*.py"))

    print(f"Found {len(plugin_files)} plugin files")
    print("-" * 80)
    print()

    for plugin_path in plugin_files:
        plugin_name = plugin_path.stem

        if plugin_name in [
            "novaprinter",
            "nova2",
            "helpers",
            "socks",
            "download_proxy",
        ]:
            continue

        print(f"\n📋 Checking: {plugin_name}")
        print("-" * 40)

        test_plugin_structure(plugin_path)
        check_plugin_file(plugin_path)

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"✅ Passed:  {RESULTS['passed']}")
    print(f"❌ Failed:  {RESULTS['failed']}")
    print(f"⚠️  Warnings: {RESULTS['warnings']}")
    print()

    if RESULTS["failed"] > 0:
        print("FAILED PLUGINS:")
        for detail in RESULTS["details"]:
            if detail["status"] == "failed":
                print(f"  - {detail['plugin']}: {detail['test']}")
                if detail["message"]:
                    print(f"    {detail['message']}")
        print()

    success_rate = (
        (RESULTS["passed"] / (RESULTS["passed"] + RESULTS["failed"])) * 100
        if (RESULTS["passed"] + RESULTS["failed"]) > 0
        else 0
    )

    print(f"Success Rate: {success_rate:.1f}%")
    print()

    if RESULTS["failed"] == 0:
        print("✅ ALL PLUGINS VALIDATED SUCCESSFULLY!")
        return True
    else:
        print("❌ SOME PLUGINS NEED ATTENTION")
        return False


if __name__ == "__main__":
    success = run_all_checks()
    sys.exit(0 if success else 1)
