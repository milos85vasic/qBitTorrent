# Operator 101: Your First Search

A hands-on tour of the merge-search dashboard from a clean clone.
Follow along in a terminal; by the end you will have run your first
search, downloaded a legal freeleech torrent, and verified it inside
the qBittorrent WebUI proxy.

## Audience

End users and fleet operators. No Python or Angular knowledge
required.

## Prerequisites

- Linux or macOS with `git`, `bash`, and one container runtime
  (`podman` preferred, `docker` supported).
- Ports `7185`, `7186`, `7187`, `7188` free on localhost.
- A browser for the dashboard (`http://localhost:7187`) and the
  WebUI proxy (`http://localhost:7186`).

## Runtime

Roughly **6 minutes** end to end once containers are pulled. First
run may take 2–3 minutes longer while `lscr.io/linuxserver/qbittorrent`
downloads.

## What you will see

- Clone + setup.
- `./start.sh` bringing up both containers.
- Dashboard landing page with the 12 default trackers.
- A search for "Ubuntu ISO" returning results from every public
  tracker.
- Clicking a magnet result and verifying the torrent arrives in
  qBittorrent at `http://localhost:7186`.
- Clean shutdown with `./stop.sh`.

## Files

| File        | What it is                                           |
|-------------|------------------------------------------------------|
| `script.md` | Narration with `[mm:ss]` scene markers.              |
| `demo.sh`   | Non-interactive shell replay of the same steps.      |
| `demo.cast` | Asciinema v2 recording. Placeholder until recorded.  |

## Next

After this track, either:

- Continue to [`02-plugin-author/`](../02-plugin-author/README.md) to
  write your own search plugin, or
- Skip to [`04-security-ops/`](../04-security-ops/README.md) for the
  operational story (credentials, scanning, observability).
