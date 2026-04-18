# Authoring a new nova3 search plugin — Narration

An ~8-minute walkthrough from an empty file to a merge-service smoke
test, without leaving the terminal.

---

## [00:00] Intro

> In this course we will write a brand-new nova3 plugin. A plugin is
> a single `.py` file that exposes four attributes and two methods,
> and runs inside a subprocess the merge service spawns per query.
> No framework, no async — just a class that prints results to stdout
> in a format the merge service parses back.

## [00:20] The plugin contract

> Every plugin class must expose:
>
> - `url` — the tracker home page, used for display only.
> - `name` — the human-readable tracker name.
> - `supported_categories` — a dict mapping qBittorrent categories
>   like `"movies"` to tracker-native category IDs.
> - `search(self, query, category="all")` — the work method. It
>   iterates tracker results and calls `prettyPrinter.print()` on
>   each one as a dict.
> - `download_torrent(self, url)` — given a detail URL, prints the
>   magnet URI to stdout so the merge service can enqueue it.

## [00:50] novaprinter contract

> `prettyPrinter.print(d)` expects a dict with these keys:
> `link` (magnet or .torrent URL), `name` (title), `size` (bytes or
> human-readable), `seeds`, `leech`, `engine_url` (the tracker home),
> and `desc_link` (detail page). Missing keys default to `-1` or
> `""`. The merge service normalises these later via the enricher —
> so it is fine to emit a minimal row.

## [01:30] Scaffolding a plugin

> Create `plugins/mytracker.py`. We start with the stub — the
> minimum nova3 will accept.

```python
# SPDX-License-Identifier: GPL-2.0-or-later
try:
    from novaprinter import prettyPrinter
    from helpers import retrieve_url
except ImportError:
    # Fallback when run standalone (local dev).
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
        html = retrieve_url(query)
        for row in self._parse(html):
            prettyPrinter(row)

    def download_torrent(self, info):
        print(info)

    def _parse(self, html):
        # Replace with real parsing — BeautifulSoup or regex.
        return []
```

## [03:00] Syntax check

> Compile-check the file before installing. Nova3 plugins are
> imported directly; a `SyntaxError` will kill the whole search
> subprocess.

```bash
python3 -m py_compile plugins/mytracker.py
```

## [03:20] Install into the container

> `install-plugin.sh` copies the file into
> `config/qBittorrent/nova3/engines/` inside the container and
> restarts the nova3 engine index.

```bash
./install-plugin.sh mytracker
./install-plugin.sh --verify
```

## [04:00] Smoke-test against the merge service

> The merge service discovers installed plugins on startup, so
> restart it after the install.

```bash
./start.sh
curl -s 'http://localhost:7187/api/trackers' | grep -i mytracker
```

> A successful response means the merge service sees your plugin.
> From the dashboard, run a search; your tracker appears alongside
> the canonical 12. If it returns zero rows, that is expected — the
> `_parse` method is still a stub.

## [05:00] Filling in _parse

> The rest of the work is HTML parsing. Use `requests` +
> `BeautifulSoup`, or `lxml`, or stdlib-only `html.parser` — the
> merge service does not care. Keep `search()` synchronous: the
> nova3 runner is not asyncio.

## [06:00] Constitution amendment for promotion

> Your plugin runs, but it is not in the canonical 12. Principle II
> of the constitution pins the default roster. To promote, open an
> amendment PR with:
>
> - A `.specify/memory/constitution.md` change bumping the minor
>   version.
> - An entry in `install-plugin.sh`'s curated list.
> - Tests under `tests/unit/` that smoke-exercise the plugin with
>   recorded HTML fixtures.

## [06:30] Recap

> You wrote a plugin class, compile-checked it, installed it, and
> saw the merge service pick it up. Promotion to the canonical 12 is
> a governance step — not a code step — so drop by
> `courses/03-contributor/` to learn the TDD cadence for landing
> that amendment.
