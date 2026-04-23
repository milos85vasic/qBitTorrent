#!/usr/bin/env python3
"""
Plugin Update Automation Tool

This tool:
1. Checks for updates to plugins from upstream sources
2. Downloads updated plugin files
3. Validates new plugins before installation
4. Creates backups of existing plugins
5. Generates update reports

Usage:
    python3 tools/plugin_update_automation.py --check
    python3 tools/plugin_update_automation.py --update
    python3 tools/plugin_update_automation.py --update --dry-run
"""

import os
import sys
import json
import argparse
import shutil
import hashlib
from datetime import datetime
from typing import Dict, List
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# Setup paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
PLUGINS_DIR = os.path.join(PROJECT_DIR, "plugins")
sys.path.insert(0, PLUGINS_DIR)


class Colors:
    GREEN = "\033[92m"
    FAIL = "\033[91m"
    WARNING = "\033[93m"
    CYAN = "\033[96m"
    BLUE = "\033[94m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def print_success(text):
    print(f"{Colors.GREEN}✓ {text}{Colors.ENDC}")


def print_error(text):
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_warning(text):
    print(f"{Colors.WARNING}! {text}{Colors.ENDC}")


def print_info(text):
    print(f"{Colors.CYAN}ℹ {text}{Colors.ENDC}")


def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{text}{Colors.ENDC}")


# Known upstream sources for plugins
UPSTREAM_SOURCES = {
    "eztv": "https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/eztv.py",
    "jackett": "https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/jackett.py",
    "limetorrents": "https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/limetorrents.py",
    "piratebay": "https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/piratebay.py",
    "solidtorrents": "https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/solidtorrents.py",
    "torlock": "https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/torlock.py",
    "torrentproject": "https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/torrentproject.py",
    "torrentscsv": "https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/torrentscsv.py",
    "academictorrents": "https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/academictorrents.py",
    "bt4g": "https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/bt4g.py",
    "glotorrents": "https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/glotorrents.py",
    "kickass": "https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/kickasstorrents.py",
    "linuxtracker": "https://raw.githubusercontent.com/MadeOfMagicAndWires/qBit-plugins/master/engines/linuxtracker.py",
    "nyaa": "https://raw.githubusercontent.com/MadeOfMagicAndWires/qBit-plugins/master/engines/nyaasi.py",
}


class PluginUpdateManager:
    """Manages plugin updates from upstream sources."""

    def __init__(self, plugins_dir: str, backup_dir: str = None):
        self.plugins_dir = plugins_dir
        self.backup_dir = backup_dir or os.path.join(plugins_dir, ".backups")

    def check_for_updates(self) -> List[Dict]:
        """Check all plugins for available updates."""
        print_header("CHECKING FOR PLUGIN UPDATES")

        updates_available = []

        for plugin_name, url in UPSTREAM_SOURCES.items():
            try:
                local_path = os.path.join(self.plugins_dir, f"{plugin_name}.py")

                if not os.path.exists(local_path):
                    print_info(f"{plugin_name}: Not installed locally")
                    updates_available.append({"plugin": plugin_name, "status": "not_installed", "upstream_url": url})
                    continue

                local_hash = self._get_file_hash(local_path)
                upstream_content = self._download_url(url)

                if upstream_content is None:
                    print_warning(f"{plugin_name}: Could not fetch upstream")
                    continue

                upstream_hash = hashlib.md5(upstream_content.encode()).hexdigest()

                if local_hash != upstream_hash:
                    local_version = self._extract_version(local_path)
                    upstream_version = self._extract_version_from_content(upstream_content)

                    print_info(f"{plugin_name}: Update available ({local_version} -> {upstream_version})")
                    updates_available.append(
                        {
                            "plugin": plugin_name,
                            "status": "update_available",
                            "local_version": local_version,
                            "upstream_version": upstream_version,
                            "upstream_url": url,
                            "upstream_content": upstream_content,
                        }
                    )
                else:
                    print_success(f"{plugin_name}: Up to date")

            except Exception as e:
                print_error(f"{plugin_name}: Error checking - {e}")

        return updates_available

    def update_plugin(self, plugin_name: str, upstream_content: str, dry_run: bool = False) -> Dict:
        """Update a single plugin."""
        result = {
            "plugin": plugin_name,
            "timestamp": datetime.now().isoformat(),
            "dry_run": dry_run,
            "status": "pending",
        }

        local_path = os.path.join(self.plugins_dir, f"{plugin_name}.py")

        try:
            if not self._validate_plugin(upstream_content):
                result["status"] = "failed"
                result["error"] = "Validation failed"
                return result

            if dry_run:
                result["status"] = "dry_run_success"
                print_info(f"{plugin_name}: Would update (dry run)")
                return result

            if os.path.exists(local_path):
                backup_path = self._create_backup(local_path)
                result["backup"] = backup_path

            with open(local_path, "w", encoding="utf-8") as f:
                f.write(upstream_content)

            result["status"] = "success"
            print_success(f"{plugin_name}: Updated successfully")

        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            print_error(f"{plugin_name}: Update failed - {e}")

        return result

    def _get_file_hash(self, filepath: str) -> str:
        """Calculate MD5 hash of a file."""
        with open(filepath, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()

    def _download_url(self, url: str, timeout: int = 30) -> str | None:
        """Download content from URL."""
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=timeout) as response:
                return response.read().decode("utf-8")
        except (URLError, HTTPError):
            return None

    def _extract_version(self, filepath: str) -> str:
        """Extract version from plugin file."""
        try:
            with open(filepath, encoding="utf-8") as f:
                content = f.read()
            return self._extract_version_from_content(content)
        except:
            return "unknown"

    def _extract_version_from_content(self, content: str) -> str:
        """Extract version from plugin content."""
        import re

        version_match = re.search(r"# VERSION:\s*([\d.]+)", content)
        if version_match:
            return version_match.group(1)
        return "unknown"

    def _validate_plugin(self, content: str) -> bool:
        """Validate plugin syntax."""
        try:
            compile(content, "<string>", "exec")
            return True
        except SyntaxError:
            return False

    def _create_backup(self, filepath: str) -> str:
        """Create backup of existing plugin."""
        os.makedirs(self.backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.basename(filepath)
        backup_name = f"{filename}.{timestamp}.bak"
        backup_path = os.path.join(self.backup_dir, backup_name)

        shutil.copy2(filepath, backup_path)
        return backup_path


def main():
    parser = argparse.ArgumentParser(description="Plugin Update Automation Tool")
    parser.add_argument("--check", action="store_true", help="Check for updates only")
    parser.add_argument("--update", action="store_true", help="Apply available updates")
    parser.add_argument("--plugin", type=str, help="Update specific plugin")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be updated")
    parser.add_argument("--output", type=str, default="plugin_update_report.json", help="Output file")
    args = parser.parse_args()

    manager = PluginUpdateManager(PLUGINS_DIR)

    if args.check or args.update:
        updates = manager.check_for_updates()

        if args.update:
            print_header("APPLYING UPDATES")
            results = []

            for update in updates:
                if update["status"] in ["update_available", "not_installed"]:
                    if args.plugin and update["plugin"] != args.plugin:
                        continue

                    if "upstream_content" in update:
                        result = manager.update_plugin(
                            update["plugin"], update["upstream_content"], dry_run=args.dry_run
                        )
                        results.append(result)

            report = {
                "timestamp": datetime.now().isoformat(),
                "total_checked": len(UPSTREAM_SOURCES),
                "updates_found": len([r for r in results if r.get("status") == "success"]),
                "results": results,
            }
        else:
            report = {
                "timestamp": datetime.now().isoformat(),
                "total_checked": len(UPSTREAM_SOURCES),
                "updates_found": len([u for u in updates if u.get("status") == "update_available"]),
                "results": updates,
            }

        with open(args.output, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\n{Colors.CYAN}Report saved to: {args.output}{Colors.ENDC}")

        return 0 if report["updates_found"] == 0 else 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
