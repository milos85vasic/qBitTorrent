# Contributor deep-dive: TDD + rebuild-reboot — Narration

~10-minute walkthrough of the contributor loop as it is actually
enforced in CI. Every scene corresponds to a block of `demo.sh` in
this directory.

---

## [00:00] Intro

> This repository treats TDD as a hard constraint, not a style
> preference. `CLAUDE.md` spells it out: write a failing test first,
> watch it fail, write the minimal code to pass, then rebuild and
> reboot the running containers, **then** commit. We will walk the
> whole loop live.

## [00:30] The five-step cadence

> 1. **RED** — write the test.
> 2. **Watch it fail** — run pytest, confirm the failure is the one
>    you expected.
> 3. **GREEN** — write the minimal implementation.
> 4. **Rebuild-reboot** — stop containers, drop `__pycache__`,
>    rebuild, restart, curl-verify the served content matches what
>    you committed.
> 5. **Commit** — only now. Never before.

## [01:15] Service fixtures replace runtime skips

> Phase 0.3 removed every `pytest.skip("service not reachable")` in
> the integration suite. Those skips made CI silently green when
> containers were down. Today, integration tests request the
> `merge_service_up` fixture from `tests/fixtures/services.py`;
> the fixture either returns a healthy base URL or marks the test
> as `ERROR` (not skipped) with a loud stacktrace. That is the
> distinction: errors surface; skips disappear.

## [02:00] Writing a failing test

> Imagine a bug report: the merge service sometimes returns
> duplicate titles across trackers. We will lock the invariant with
> a test. This test lives under `tests/unit/` because it asserts a
> pure-function dedup invariant.

```python
# tests/unit/test_dedup_invariant.py
from download_proxy.src.merge_service.deduplicator import dedup_titles


def test_dedup_titles_collapses_identical_case_insensitive():
    rows = [
        {"name": "Ubuntu 24.04 ISO", "size": 1_000_000, "seeds": 10},
        {"name": "ubuntu 24.04 iso", "size": 1_000_000, "seeds":  7},
    ]
    out = dedup_titles(rows)
    assert len(out) == 1
    assert out[0]["seeds"] == 10  # higher-seeded winner kept
```

## [02:45] Watching the RED

> Run only this file so the signal is clean.

```bash
python3 -m pytest tests/unit/test_dedup_invariant.py -v --import-mode=importlib
```

> Expected outcome: `AssertionError` or `ImportError`. **Do not**
> proceed until you see the failure. If pytest passes immediately,
> the test is wrong — rewrite it.

## [03:30] Writing the GREEN implementation

> The minimal change that turns the RED to GREEN — nothing more.
> Guard against over-engineering by keeping the diff surgical.

```python
# download-proxy/src/merge_service/deduplicator.py
def dedup_titles(rows):
    seen = {}
    for row in rows:
        key = row["name"].strip().lower()
        existing = seen.get(key)
        if existing is None or row["seeds"] > existing["seeds"]:
            seen[key] = row
    return list(seen.values())
```

## [04:15] Re-run the test

> Same command, this time you want a green run. Capture the elapsed
> time — Phase 3.1 sets a 30-second soft budget per unit test.

```bash
python3 -m pytest tests/unit/test_dedup_invariant.py -v --import-mode=importlib
```

## [05:00] The mandatory rebuild-reboot

> The running container still has the **old** bytecode. Committing
> now ships code that nobody has run in-environment. `CLAUDE.md`
> requires this cycle:

```bash
./stop.sh
# drop stale pyc bytecode inside the running image
podman exec qbittorrent-proxy sh -lc 'find /app -name __pycache__ -exec rm -rf {} +' || true
./start.sh -p
# sanity-check: is the new code actually served?
curl -s http://localhost:7187/ | grep -q 'merge-service'
```

## [06:00] Coverage ratchet

> `pyproject.toml` carries a `fail_under` threshold for pytest-cov.
> Every successful PR raises the number; CI rejects a PR that drops
> coverage. If your change is a pure refactor with no new code,
> coverage is unchanged — that is fine.

```bash
python3 -m pytest --cov=download_proxy --cov-report=term-missing \
    --cov-fail-under="$(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml","rb"))["tool"]["coverage"]["report"]["fail_under"])')"
```

## [07:00] Running the scanners locally

> `./scripts/scan.sh --all` runs ruff, bandit, pip-audit, and
> gitleaks against the current tree, writing SARIF to
> `artifacts/scans/`. CI runs the same set; running locally first
> costs ~45 seconds and avoids a failed PR check.

```bash
./scripts/scan.sh --all
ls artifacts/scans/
```

## [07:45] Opening the PR

> Push the feature branch. `.github/workflows/test.yml` is now a
> multi-job matrix (split in Phase 0.4). Expect:
>
> - `lint` — ruff + bandit.
> - `unit` — fast suite, hard coverage gate.
> - `integration` — service-fixture-backed, real containers.
> - `scan` — pip-audit + gitleaks + trivy.

```bash
git push -u origin feature/dedup-invariant
gh pr create --fill
```

## [08:30] What reviewers check

> Reviewers read three things in order:
>
> 1. The test — is the invariant meaningful?
> 2. The diff — is it minimal?
> 3. The PR description's **Test plan** — did you list the manual
>    smoke steps you ran after rebuild-reboot?

## [09:15] Recap

> RED, watch fail, GREEN, rebuild-reboot, commit. Coverage only
> goes up. Scanners pre-empt CI. The fixtures in
> `tests/fixtures/services.py` turn environmental flakes into
> noisy errors, not silent skips. That is the contributor loop —
> no shortcuts.
