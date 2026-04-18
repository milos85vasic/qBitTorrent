# Operator 101: Your First Search — Narration

A ~6-minute walkthrough from a clean clone to a downloaded torrent.
Every `[mm:ss]` marker is a scene cue for the voice-over; `demo.sh`
in this directory replays the exact commands in the same order.

---

## [00:00] Intro

> Welcome. In the next six minutes you will clone qBittorrent-Fixed,
> bring the containers up, run your first merge search, and download
> a freeleech torrent — all without touching a tracker configuration
> file. If you have used qBittorrent's WebUI before, this will feel
> familiar; the new surface is the merge-search dashboard on port
> 7187.

## [00:15] Clone and enter the repo

> First, a shallow clone. We are on `main`; production operators
> should pin to a release tag in real deployments.

```bash
git clone --depth 1 https://github.com/milos85vasic/qBitTorrent.git
cd qBitTorrent
```

## [00:30] One-time setup

> `./setup.sh` prepares the `.env` template, the `config/` volume,
> and verifies the container runtime. It is idempotent — safe to
> re-run.

```bash
./setup.sh
```

## [00:45] Start the containers

> `./start.sh` launches both containers. `-p` pulls the latest
> images first; on a warm machine you can omit it.

```bash
./start.sh -p
```

> You should see **qbittorrent** bound on `:7185` (proxied to
> `:7186`) and **qbittorrent-proxy** on `:7186` and `:7187`.
> Note: The webui-bridge on `:7188` runs as a host process, not a
> container — we do not need it for public-tracker searches today.

## [01:15] Open the dashboard

> Point a browser at `http://localhost:7187`. The top header shows
> the merge-service status and the configured trackers. Twelve
> public plugins are installed by default.

```bash
# Simulated browse:
curl -s http://localhost:7187/ | head -n 5
```

## [01:45] Run a search

> In the search box, type `Ubuntu ISO`. The dashboard uses
> server-sent events — results from each tracker stream in as they
> arrive.

```bash
curl -s 'http://localhost:7187/api/search?q=Ubuntu%20ISO&trackers=piratebay,eztv' \
  | head -c 400
```

> You see the first batch of JSON payloads containing title, size,
> seeders, and an enriched quality tag (`1080p`, `2160p`, etc.).

## [02:30] Browse results

> Back in the browser, results are sorted by seeders by default.
> The **Quality** column collapses identical releases across
> trackers — dedup works across RuTracker, PirateBay, SolidTorrents,
> and friends.

## [03:00] Download via magnet

> Pick a healthy freeleech result. Click the download button; the
> dashboard opens a confirmation dialog, then POSTs to
> `/api/download` with the magnet URI. The download proxy on
> `:7186` forwards it to the qBittorrent WebUI with admin
> credentials already injected — you never type them.

```bash
# A magnet download via the API:
curl -s -X POST http://localhost:7187/api/download \
  -H 'Content-Type: application/json' \
  -d '{"magnet":"magnet:?xt=urn:btih:EXAMPLEUBUNTUISO","tracker":"piratebay"}'
```

## [04:00] Verify in qBittorrent WebUI proxy

> Open `http://localhost:7186`. The proxy has already logged you in
> as `admin / admin`. You should see the new torrent in
> **Downloading** state.

```bash
curl -s -u admin:admin http://localhost:7186/api/v2/torrents/info \
  | head -c 300
```

> If authentication fails here, re-run `./init-qbit-password.sh` —
> that script forces the qBittorrent container back to the
> hardcoded admin credentials.

## [05:00] Stop cleanly

> When you are done, stop both containers. Data under
> `QBITTORRENT_DATA_DIR` (default `/mnt/DATA`) persists between
> runs; `./stop.sh` only shuts the containers down.

```bash
./stop.sh
```

## [05:30] Recap

> You just ran a merge search across multiple trackers, downloaded a
> torrent without ever typing a credential, and tore everything down
> in a single command. Next up: authoring your own search plugin —
> see `courses/02-plugin-author/`.
