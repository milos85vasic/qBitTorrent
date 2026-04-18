# tmp/ — Shared Scratch Volume

This directory is the **shared scratch volume** for inter-container
file exchange, as required by constitution Principle I
(Container-First Architecture):

> Volume mounts MUST use the shared `tmp/` directory for inter-container
> file exchange (torrent files, temporary downloads).

Both containers bind-mount it from the repo root into their own
filesystems:

| Container | Mount point | Read/Write |
|---|---|---|
| `qbittorrent` | `/shared-tmp` | rw |
| `qbittorrent-proxy` | `/shared-tmp` | rw |

See `docker-compose.yml` — both services have
`./tmp:/shared-tmp` in their `volumes:` list.

## What lives here

At runtime this directory holds:

- Fetched `.torrent` files that the proxy retrieved from a private
  tracker and is handing off to qBittorrent for loading.
- Partially decoded magnet metadata.
- `pip`-install scratch (`pip-build-tracker-*`, `pip-metadata-*`,
  `pip-unpack-*`) — the Python 3.12 image uses `TMPDIR=/shared-tmp`
  (set in `docker-compose.yml`) so pip lays its working trees here
  during `start-proxy.sh`.
- Any other short-lived artefact the two containers need to exchange.

Nothing here is authoritative state. The directory can be wiped at
any time while the stack is stopped without data loss.

## What is committed

**Nothing.** The directory itself is tracked (so the bind-mount
resolves on a fresh checkout) but every file in it is gitignored.

## Retention

`tmp/` is not auto-pruned today. If disk pressure rises:

```bash
./stop.sh                 # stop both containers first
find tmp/ -mindepth 1 -delete
./start.sh -p
```

Do **not** prune `tmp/` while the stack is running — pip may be
writing here during a restart cycle and the qbittorrent container
may be reading a torrent file handed to it by the proxy.

## Tests

- `tests/integration/test_live_containers.py` exercises the handoff
  path that depends on this directory.
- `tests/unit/test_ci_infra.py` asserts that `tmp/` exists and is
  bind-mounted from the compose file.

## Gotchas

- The directory mode is **777** and is shared between UID namespaces.
  On rootless podman the container-side UID remaps to a sub-UID; the
  mode has to be liberal enough for both the proxy (root in the
  container) and qBittorrent (`PUID=1000`).
- On systems with `TMPDIR` inherited from the shell, the container
  still uses `/shared-tmp` because `docker-compose.yml` sets
  `TMPDIR=/shared-tmp` on the proxy service.
- Do not commit anything from here. If a test needs a scratch
  directory, use `pytest`'s `tmp_path` fixture instead.
