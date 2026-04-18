#!/usr/bin/env bash
# Authoring a new nova3 search plugin — replayable demo.
#
# Re-plays: scaffold a plugin, py_compile it, install it via
# install-plugin.sh --verify, smoke-check the merge service saw it.
# Non-interactive: no privilege escalation, no stdin reads, no
# prompts.

set -euo pipefail

TMPDIR_PLUGIN="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_PLUGIN"' EXIT

PLUGIN_FILE="$TMPDIR_PLUGIN/mytracker.py"

say() {
    printf '\n>>> %s\n' "$*"
}

say "[00:00] Authoring a new nova3 plugin"
say "Creating a minimal scaffold at $PLUGIN_FILE"

cat >"$PLUGIN_FILE" <<'PLUGIN_EOF'
# SPDX-License-Identifier: GPL-2.0-or-later
"""Demonstration nova3 plugin. Safe to compile; parses nothing real."""

try:
    from novaprinter import prettyPrinter
    from helpers import retrieve_url
except ImportError:
    def prettyPrinter(d):
        print(d)

    def retrieve_url(url):
        import urllib.request
        return urllib.request.urlopen(url).read().decode("utf-8", "replace")


class mytracker:
    url = "https://example.tracker.invalid"
    name = "Mytracker"
    supported_categories = {"all": "0", "movies": "1", "tv": "2"}

    def search(self, what, cat="all"):
        category = self.supported_categories.get(cat, "0")
        query = f"{self.url}/search?q={what}&cat={category}"
        _ = query  # parsing omitted in demo stub

    def download_torrent(self, info):
        print(info)
PLUGIN_EOF

say "[03:00] py_compile sanity check"
python3 -m py_compile "$PLUGIN_FILE"
echo "  OK: $(basename "$PLUGIN_FILE") compiles cleanly."

say "[03:20] Install via install-plugin.sh (--verify is idempotent)"
echo "  ./install-plugin.sh mytracker"
echo "  ./install-plugin.sh --verify"

say "[04:00] Smoke-test against the merge service"
echo "  curl -s 'http://localhost:7187/api/trackers' | grep -i mytracker"

say "[05:00] Next: fill in _parse with real HTML extraction."
say "[06:00] For promotion to the canonical 12, open a constitution amendment."
say "[06:30] Done. Continue with courses/03-contributor/."
