# Upstreams/ — Upstream Repository Pointer

This directory holds pointers to the upstream repositories this project
depends on or re-publishes to. It is intentionally small — one file
per upstream — and is consumed by lifecycle scripts that need to know
"where does this go when we push?".

## Contents

| File | Purpose |
|---|---|
| `GitHub.sh` | Exports `UPSTREAMABLE_REPOSITORY` — the canonical GitHub URL of this project. Sourced by upstream-publish scripts. |

### `GitHub.sh`

```sh
export UPSTREAMABLE_REPOSITORY="git@github.com:milos85vasic/qBitTorrent.git"
```

Sourced by any script that needs to `git push` to the canonical remote
without hard-coding the URL.

## Conventions

- One file per upstream; filename is the upstream platform
  (`GitHub.sh`, `GitLab.sh`, `Codeberg.sh`, …).
- Each file is a shell script that exports **one** environment
  variable named after its purpose
  (`UPSTREAMABLE_REPOSITORY`, `MIRROR_REPOSITORY`, …).
- Executable bit is required (`chmod +x`) so the file can be sourced
  or invoked.
- No credentials in this directory. Authentication is SSH-key or
  environment-token, not embedded URLs.

## Tests

No dedicated tests. The file is sourced at push time and a missing
environment variable surfaces immediately.

## Gotchas

- If a fork wants to push to a different remote, override the variable
  in shell before invoking the publish script — do not edit `GitHub.sh`
  in place, or a stray commit will leak the override.
- The permissions are `rwxr-x---` by design — only the owner can
  source the file.
