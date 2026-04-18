# plugins/ — qBittorrent nova3 Search Engines

This directory holds every search-engine plugin used by the merge
service and the vanilla qBittorrent `nova3` search layer. Each `.py`
file is a self-contained engine that conforms to the qBittorrent
nova3 contract.

## The nova3 plugin contract

Per constitution Principle II, every plugin **must**:

1. Declare class attributes `url`, `name`, and
   `supported_categories` (dict mapping category name to the engine's
   internal ID string).
2. Implement `search(self, what, cat='all')` and emit results
   exclusively through `novaprinter.prettyPrinter({...})`.
3. Implement `download_torrent(self, url)` returning a magnet link,
   a temp-file path, or writing the raw bytes to stdout.
4. Use `try: import novaprinter ... except ImportError:` so the plugin
   can still be imported outside the container for unit tests.
5. Pass `python3 -m py_compile` before it is deployed — the install
   script enforces this.

## The canonical 12 (constitution II)

The `install-plugin.sh` managed list ships exactly these twelve plugins
to `config/qBittorrent/nova3/engines/` inside the `qbittorrent`
container:

```
eztv jackett limetorrents piratebay solidtorrents torlock
torrentproject torrentscsv rutracker rutor kinozal nnmclub
```

Rationale: this roster gives coverage of general torrents (piratebay,
limetorrents, rutor), TV (eztv), aggregator (jackett), metadata
(torrentproject, torrentscsv, solidtorrents, torlock), and the three
CIS-region private trackers the project supports (rutracker, kinozal,
nnmclub).

IPTorrents is handled by the merge service directly rather than via a
nova3 plugin because of its cookie/referer requirements.

## The other 36

Every additional `.py` file here is a **community contribution** that
is *not* installed by default. Phase 4 of the completion-initiative
plan adds per-plugin tests, installation paths, and documentation for
the 36 community plugins. Until that lands they are:

- Syntactically valid (guarded by `ci.sh --quick`).
- Not pinned to any qBittorrent version.
- Not part of the CI suite.
- Safe to keep on disk — they will only execute if a user explicitly
  copies them into the container's engines directory.

A non-exhaustive list: `academictorrents`, `ali213`, `anilibra`,
`audiobookbay`, `bitru`, `bt4g`, `btsow`, `extratorrent`, `gamestorrents`,
`glotorrents`, `kickass`, `linuxtracker`, `megapeer`, `nyaa`, `one337x`,
`pctorrent`, `pirateiro`, `rockbox`, `snowfl`, `therarbg`, `tokyotoshokan`,
`torrentdownload`, `torrentfunk`, `torrentgalaxy`, `torrentkitty`,
`xfsub`, `yihua`, `yourbittorrent`, `yts`.

## How install-plugin.sh works

```
./install-plugin.sh [--list | --all | <name> ...]
```

The script:

1. Detects the container runtime (podman preferred, docker fallback).
2. Copies each selected `.py` (and matching `.json`, `.png`) from
   `plugins/` into the `qbittorrent` container at
   `/config/qBittorrent/nova3/engines/`.
3. Runs `python3 -m py_compile` inside the container against each new
   file and refuses to proceed if syntax is invalid.
4. Restarts the qBittorrent search engine (nova3 reloads on next search).

`install-plugin.sh --all` is intentionally **not** the full 48-plugin
dump; it expands to the twelve-plugin canonical roster above.

## Support files

- `novaprinter.py`, `nova2.py` — the nova3 runtime shim + abstract
  base classes distributed with qBittorrent upstream. Do not edit.
- `helpers.py` — shared utility helpers used by many plugins.
- `env_loader.py` — reads tracker credentials (see the environment
  variable priority in `CLAUDE.md`).
- `download_proxy.py` — the HTTP server listening on port **7186**
  that intercepts authenticated tracker downloads. Part of this
  directory because it is copied to `engines/` alongside the plugins
  and imports the `jackett` helper code.
- `socks.py` — vendored pure-Python SOCKS client. Contains an
  intentional `NotImplementedError` for UDP fragmentation that has
  been acknowledged but not yet implemented; TCP path works.
- `jackett.py`, `jackett.json` — Jackett adapter (needs a running
  Jackett at the URL in `jackett.json`).
- `webui_compatible/` — alternate implementations of `kinozal`,
  `nnmclub`, `rutracker` used when the WebUI-bridge path is active
  (constitution Principle V).

## How to write a new plugin

1. Copy an existing plugin as a template. `eztv.py` is the smallest
   public-tracker example; `kinozal.py` is the richest private-tracker
   example.
2. Follow the contract above. Emit via `prettyPrinter`, never return a
   list.
3. Add a matching `.json` and `.png` if your engine has a custom icon.
4. Write a unit test in `tests/unit/` that imports the class and
   monkey-patches `novaprinter.prettyPrinter` to capture output.
5. Run `./ci.sh --quick` to syntax-check.
6. If the plugin is worth canonicalising, amend `install-plugin.sh` and
   this README's twelve-plugin list, and move it through a PR.

## Tests

- Every canonical plugin has a search test in
  `tests/unit/test_merge_trackers.py` via the orchestrator.
- Freeleech and private-tracker behaviour is in
  `tests/unit/test_freeleech.py` and `tests/unit/test_private_tracker_search.py`.
- Subprocess integration is exercised in
  `tests/unit/test_public_tracker_subprocess.py`.
- Tracker validation lives in `tests/unit/test_tracker_validator.py`.

## Gotchas

- The merge service runs plugins out of process
  (`asyncio.create_subprocess_exec python3 -c ...`) with a 10-second
  timeout — any plugin that blocks on input or prompts interactively
  will silently produce zero results.
- Plugins must **never** import from the merge service. The dependency
  direction is one-way (merge-service → plugins via subprocess).
- A plugin that mutates global state at import time will leak state
  across tests. Stick to instance state on the class.
- Private-tracker plugins MUST read credentials from environment
  variables — hard-coded credentials are a CI failure and a
  constitution III violation.
- Icons (`*.png`) are optional; they only affect the qBittorrent UI.
