# Courses — Asciinema Video Tracks

This directory holds the **narrated, recordable video courses** for
qBittorrent-Fixed. Every course is pure text on disk: narration in
Markdown, shell commands in a reproducible `demo.sh`, and an Asciinema
cast file that plays back the demo in a real terminal. There are no
binary assets in this tree — no mp4, no webm, no gif. That keeps the
repository diff-friendly and lets reviewers read the full script
alongside the commands that produce it.

The site embeds each cast with the
[asciinema-player](https://github.com/asciinema/asciinema-player) so
viewers watch the terminal session in the browser without ever
downloading a video. When the player is not available (e.g. rendering
on GitHub), readers can still follow `script.md` + `demo.sh` by hand.

## Layout

Every course lives in its own numbered directory:

```
courses/
├── README.md                 (this file)
├── 01-operator/              Your first search — end-user track
│   ├── README.md             Audience, prerequisites, runtime
│   ├── script.md             Narration with [mm:ss] scene markers
│   ├── demo.sh               The exact shell commands the cast replays
│   └── demo.cast             Asciinema v2 recording (placeholder)
├── 02-plugin-author/         Authoring a nova3 search plugin
│   └── ...
├── 03-contributor/           Contributor deep-dive: TDD + rebuild-reboot
│   └── ...
└── 04-security-ops/          Security and operations
    └── ...
```

Each track directory contains exactly four files:

| File         | Purpose                                                              |
|--------------|----------------------------------------------------------------------|
| `README.md`  | One-page description (audience, prerequisites, runtime estimate).    |
| `script.md`  | Narration with timestamped scene markers like `[00:15]`, `[00:30]`. |
| `demo.sh`    | `set -euo pipefail` shell script; no sudo, no interactive prompts.   |
| `demo.cast`  | Asciinema v2 recording — scripted or interactive replay.             |

### Optional extras

- `thumbnail.txt` — ASCII-art card, since we never commit images.
- A track-local `.gitignore` to ignore raw recordings that are too big
  to track.

## Recording a cast

Two supported recording modes. Both produce a valid Asciinema v2 JSON
cast file, which is what the website embeds.

### Scripted replay (recommended)

```bash
asciinema rec demo.cast --command "bash demo.sh"
```

The `--command` flag runs the demo script as a single command inside
the recording. Because `demo.sh` is non-interactive (`set -euo
pipefail`, no `sudo`, no `read`), the run is deterministic: the cast
captures exactly the narrated sequence, no manual typing required.
Re-record any time the demo changes — the diff stays tiny.

### Interactive replay

```bash
asciinema rec demo.cast
# then type / paste the commands from demo.sh, following the script.
```

Use interactive mode when you want natural pauses for the voice-over
to breathe — the cast records real typing speed and inter-command
delays.

## Playback

From the terminal:

```bash
asciinema play demo.cast            # 1× speed
asciinema play demo.cast --speed 2  # 2× speed
```

From the rendered docs site: each course page embeds the cast with
`asciinema-player`, either via the `mkdocs-asciinema-player` plugin or
(simpler) an inline `<script src="…asciinema-player.js">` tag next to
a `<div id="player">` container. We use the inline tag because it
avoids a MkDocs plugin dependency.

## Authoring a new course

1. Pick the next two-digit prefix — `05-…`, `06-…`.
2. Copy the layout from `01-operator/`.
3. Write `script.md` first — the narration is the contract. Use
   `[mm:ss]` scene markers every 15–30 seconds so voice-over timing is
   predictable.
4. Translate every spoken instruction into `demo.sh`. If a step cannot
   be scripted (e.g. browser click), describe it in `script.md` and
   leave a matching echo'd placeholder in `demo.sh`.
5. Record the cast locally with Asciinema; commit the cast.
6. Add an entry to `mkdocs.yml` under the **Courses** section and a
   thin include file under `website/docs/courses/` that
   `include-markdown` pulls from `courses/<track>/script.md`.

## Tests that guard this tree

- `tests/unit/test_courses_scaffold.py` — enforces directory layout,
  required files, cast format, and `demo.sh` non-interactive
  invariants.
- `tests/unit/test_course_scripts_lint.py` — runs `bash -n` on every
  `demo.sh` to catch syntax errors without requiring `shellcheck`.

## Why Asciinema and not video

- **Diffability.** A cast file is newline-delimited JSON. Git diffs
  are readable, PRs are reviewable.
- **Size.** A 6-minute demo lands at ~10–80 KB instead of 30+ MB.
- **Accessibility.** The underlying text is selectable and
  screen-reader-friendly.
- **Reproducibility.** `demo.sh` + a clean clone replays the course
  end-to-end.
