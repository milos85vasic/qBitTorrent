#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive UI Automated Download Flow Test
Tests complete download workflow for all plugins with magnet links
"""

import subprocess
import time
import json
import sys
from pathlib import Path

PLUGINS_DIR = Path(__file__).parent.parent / "plugins"
PROJECT_DIR = Path(__file__).parent.parent

PLUGINS_TO_TEST = [
    ("piratebay", "ubuntu", "public"),
    ("eztv", "ubuntu", "public"),
    ("rutor", "ubuntu", "public"),
    ("rutracker", "ubuntu", "private"),
    ("kinozal", "ubuntu", "private"),
    ("nnmclub", "ubuntu", "private"),
    ("limetorrents", "ubuntu", "public"),
    ("solidtorrents", "ubuntu", "public"),
    ("torrentproject", "ubuntu", "public"),
    ("torlock", "ubuntu", "public"),
    ("torrentscsv", "ubuntu", "public"),
]

MAGNET_REGEX = r"^magnet:\?xt=urn:btih:[a-fA-F0-9]{40}"

RESULTS = {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "details": []}


def test_plugin_search(plugin_name: str, search_query: str) -> dict:
    """Test plugin search and return first result with magnet link."""
    print(f"\n🔍 Testing {plugin_name} search for '{search_query}'...")

    result = {
        "plugin": plugin_name,
        "query": search_query,
        "found_results": False,
        "has_magnet": False,
        "magnet_link": None,
        "error": None,
    }

    plugin_file = PLUGINS_DIR / f"{plugin_name}.py"
    if not plugin_file.exists():
        result["error"] = f"Plugin file not found: {plugin_file}"
        print(f"  ❌ Plugin file not found")
        return result

    try:
        test_script = f'''
import sys
sys.path.insert(0, "{PLUGINS_DIR}")
import {plugin_name}

results = []

def mock_prettyPrinter(data):
    global results
    results.append(data)

# Monkey patch prettyPrinter
import novaprinter
novaprinter.prettyPrinter = mock_prettyPrinter

try:
    engine = {plugin_name}.{plugin_name.capitalize() if plugin_name not in ["piratebay", "solidtorrents", "torrentscsv", "torrentproject"] else plugin_name.capitalize()}()
    engine.search("{search_query}")
    
    if results:
        import json
        print(json.dumps(results[0]))
except Exception as e:
    import traceback
    print(json.dumps({{"error": str(e), "traceback": traceback.format_exc()}}), file=sys.stderr)
'''

        proc = subprocess.run(
            ["python3", "-c", test_script],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(PLUGINS_DIR),
        )

        if proc.returncode != 0:
            result["error"] = proc.stderr
            print(f"  ❌ Plugin execution failed: {proc.stderr[:200]}")
            return result

        if proc.stdout.strip():
            try:
                first_result = json.loads(proc.stdout.strip())
                result["found_results"] = True

                link = first_result.get("link", "")
                if link.startswith("magnet:"):
                    result["has_magnet"] = True
                    result["magnet_link"] = link
                    print(f"  ✅ Found magnet link: {link[:80]}...")
                else:
                    result["error"] = f"Link is not a magnet: {link[:80]}"
                    print(f"  ⚠️  Link is not a magnet: {link[:80]}")

            except json.JSONDecodeError as e:
                result["error"] = f"Failed to parse result: {e}"
                print(f"  ❌ Failed to parse result")
        else:
            result["error"] = "No results found"
            print(f"  ⚠️  No results found")

    except subprocess.TimeoutExpired:
        result["error"] = "Timeout after 30 seconds"
        print(f"  ❌ Timeout")
    except Exception as e:
        result["error"] = str(e)
        print(f"  ❌ Exception: {e}")

    return result


def test_plugin_download(plugin_name: str, magnet_link: str) -> dict:
    """Test plugin download_torrent method with magnet link."""
    print(f"\n📥 Testing {plugin_name} download with magnet...")

    result = {"plugin": plugin_name, "download_works": False, "error": None}

    if not magnet_link:
        result["error"] = "No magnet link provided"
        return result

    try:
        test_script = f'''
import sys
sys.path.insert(0, "{PLUGINS_DIR}")
import {plugin_name}
import io
from contextlib import redirect_stdout

output = io.StringIO()

try:
    engine = {plugin_name}.{plugin_name.capitalize() if plugin_name not in ["piratebay", "solidtorrents", "torrentscsv", "torrentproject"] else plugin_name.capitalize()}()
    with redirect_stdout(output):
        engine.download_torrent("{magnet_link}")
    
    result = output.getvalue()
    if result:
        print(result)
except Exception as e:
    print(f"ERROR: {{e}}", file=sys.stderr)
'''

        proc = subprocess.run(
            ["python3", "-c", test_script],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(PLUGINS_DIR),
        )

        if proc.returncode == 0 and magnet_link in proc.stdout:
            result["download_works"] = True
            print(f"  ✅ Download method handles magnet correctly")
        else:
            result["error"] = proc.stderr or "Download did not output correctly"
            print(f"  ❌ Download failed: {result['error'][:200]}")

    except subprocess.TimeoutExpired:
        result["error"] = "Timeout"
        print(f"  ❌ Timeout")
    except Exception as e:
        result["error"] = str(e)
        print(f"  ❌ Exception: {e}")

    return result


def run_all_tests():
    """Run all plugin tests."""
    print("=" * 80)
    print("COMPREHENSIVE UI AUTOMATED DOWNLOAD FLOW TEST")
    print("=" * 80)
    print(f"\nTesting {len(PLUGINS_TO_TEST)} plugins...")
    print("-" * 80)

    for plugin_name, search_query, tracker_type in PLUGINS_TO_TEST:
        RESULTS["total"] += 1

        print(f"\n{'=' * 80}")
        print(f"Testing: {plugin_name.upper()} ({tracker_type} tracker)")
        print(f"{'=' * 80}")

        search_result = test_plugin_search(plugin_name, search_query)

        if search_result["error"] and "credentials" in search_result["error"].lower():
            print(f"  ⏭️  Skipping {plugin_name} - requires credentials")
            RESULTS["skipped"] += 1
            RESULTS["details"].append(
                {
                    "plugin": plugin_name,
                    "status": "skipped",
                    "reason": "requires_credentials",
                }
            )
            continue

        if search_result["has_magnet"]:
            download_result = test_plugin_download(
                plugin_name, search_result["magnet_link"]
            )

            if download_result["download_works"]:
                RESULTS["passed"] += 1
                RESULTS["details"].append(
                    {
                        "plugin": plugin_name,
                        "status": "passed",
                        "magnet_link": search_result["magnet_link"][:80],
                    }
                )
            else:
                RESULTS["failed"] += 1
                RESULTS["details"].append(
                    {
                        "plugin": plugin_name,
                        "status": "failed",
                        "reason": download_result["error"],
                    }
                )
        else:
            RESULTS["failed"] += 1
            RESULTS["details"].append(
                {
                    "plugin": plugin_name,
                    "status": "failed",
                    "reason": search_result.get("error", "no_magnet_link"),
                }
            )

        time.sleep(0.5)

    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total:   {RESULTS['total']}")
    print(f"✅ Passed:  {RESULTS['passed']}")
    print(f"❌ Failed:  {RESULTS['failed']}")
    print(f"⏭️  Skipped: {RESULTS['skipped']}")

    if RESULTS["passed"] > 0:
        print("\n✅ PASSED PLUGINS:")
        for detail in RESULTS["details"]:
            if detail["status"] == "passed":
                print(f"  - {detail['plugin']}")

    if RESULTS["failed"] > 0:
        print("\n❌ FAILED PLUGINS:")
        for detail in RESULTS["details"]:
            if detail["status"] == "failed":
                print(f"  - {detail['plugin']}: {detail.get('reason', 'unknown')}")

    if RESULTS["skipped"] > 0:
        print("\n⏭️  SKIPPED PLUGINS (need credentials):")
        for detail in RESULTS["details"]:
            if detail["status"] == "skipped":
                print(f"  - {detail['plugin']}")

    success_rate = (
        (RESULTS["passed"] / (RESULTS["total"] - RESULTS["skipped"])) * 100
        if (RESULTS["total"] - RESULTS["skipped"]) > 0
        else 0
    )
    print(f"\nSuccess Rate: {success_rate:.1f}%")

    if RESULTS["failed"] == 0:
        print("\n✅ ALL TESTED PLUGINS WORKING CORRECTLY!")
        return True
    else:
        print(f"\n⚠️  {RESULTS['failed']} plugin(s) need attention")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
