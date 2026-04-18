# config/ — Runtime Configuration Tree

This directory is the **single source of truth for runtime configuration**
(constitution Principle I). It is bind-mounted into both containers at
`/config/` by `docker-compose.yml` and becomes the on-disk state of the
qBittorrent WebUI and the download proxy.

Most of this tree is **gitignored**; only the stubs that bootstrap a
fresh checkout live in version control.

## Subdirectories

```
config/
├── qBittorrent/        # qBittorrent client state + nova3 plugins
├── download-proxy/     # merge service per-deployment files (creds, hooks)
├── merge-search/       # merge-service DB-free persistence (e.g. scheduler)
├── .cache/             # XDG cache root for the container
└── .env                # container-local env overrides (gitignored)
```

Exact sub-trees appearing on disk vary by deployment — this README
documents what is expected to exist at runtime.

## What is gitignored

Per `.gitignore`:

- `config/qBittorrent/**` — all client state, session data, cache, and
  downloaded metadata.
- `config/download-proxy/qbittorrent_creds.json` — saved
  `admin`/`admin` credentials (or user override).
- `config/download-proxy/hooks.json` — user-defined pipeline hooks.
- `config/download-proxy/src/` — stale copies of the service tree from
  prior manual `podman cp` runs. Never commit these; the canonical
  source is `download-proxy/src/` at the repo root.
- `config/merge-search/**` — any cached or scheduled-task state.
- `config/.cache/**` — XDG cache.
- `config/.env` — deployment-local overrides.

## What is committed

Only a small set of bootstrap stubs:

- `config/qBittorrent/nova3/engines/` — target location for plugins;
  the `install-plugin.sh` script populates it from `../plugins/`. The
  directory itself is committed so the bind-mount resolves on a fresh
  checkout.
- Placeholder files required to keep the directory tree alive in git
  (empty files named `CONFIG`, `SCRIPT`, `EOF` may exist — do not
  remove, see `CLAUDE.md` gotchas).

Every secret — tracker credentials, cookies, saved logins — lives
outside the repo in `.env` / `~/.qbit.env` / container env.

## How it is mounted

`docker-compose.yml`:

```yaml
volumes:
  - ./config:/config
```

Both containers see the same path. The `qbittorrent` container owns
`/config/qBittorrent/`; the `qbittorrent-proxy` container reads plugins
from there, writes credentials to `/config/download-proxy/`, and reads
hooks from `/config/download-proxy/hooks.json`.

The shared scratch volume is **`tmp/`** at the repo root, not here —
see [`../tmp/README.md`](../tmp/README.md).

## How to reset a deployment

```bash
./stop.sh --purge         # remove containers + images
rm -rf config/qBittorrent/BT_backup config/qBittorrent/sessions
rm -f  config/download-proxy/qbittorrent_creds.json
./setup.sh                 # recreate stubs
./start.sh -p              # pull + start
```

Never `rm -rf config/` wholesale — that deletes committed stubs and
will break the bind-mount.

## Tests

- `tests/unit/test_config.py` tests the env-loader priority chain.
- Integration tests rely on the config tree being writable by PUID/PGID
  = 1000.

## Gotchas

- The `config/` directory has mode `drwxrwxrwx` because the
  qBittorrent container runs as `PUID/PGID=1000` but podman rootless
  may remap IDs. Preserve the permissions or the container will fail
  to start.
- `config/download-proxy/src/` is a classic footgun: it's a stale copy
  of the service tree that someone `podman cp`'d. The runtime loads
  `/config/download-proxy/src/` over the bind-mounted host copy. If
  the container keeps running old code after an edit, check this
  path.
- `PUID` / `PGID` are read by the `lscr.io/linuxserver/qbittorrent`
  image at start and must match the owner of this tree.
- Once credentials are saved, the WebUI password is no longer
  `admin`/`admin` — run `fix-qbit-password.sh` to reset.
