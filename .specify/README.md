# .specify/ — GitSpec Constitution & Memory

This directory is the **GitSpec** (and compatible tooling, e.g. SpecKit,
OpenCode) memory area for the project. It holds three kinds of
machine-readable context that the planning and execution skills rely
on: the **constitution**, **templates**, and **integration manifests**.

The directory is committed to the repo, but nothing here is a runtime
artefact — deleting it would not break the product, only the
specification-driven workflow.

## Contents

```
.specify/
├── README.md                    # this file
├── feature.json                 # the currently active feature ID
├── init-options.json            # first-time init defaults
├── integration.json             # enabled integrations registry
├── extensions.yml               # extension definitions
├── memory/
│   └── constitution.md          # the project constitution (v1.1.0)
├── templates/
│   ├── spec-template.md
│   ├── plan-template.md
│   ├── tasks-template.md
│   ├── checklist-template.md
│   ├── constitution-template.md
│   └── agent-file-template.md
├── extensions/
│   └── git/                     # git extension config
├── integrations/
│   ├── opencode/                # OpenCode plugin config
│   ├── opencode.manifest.json
│   └── speckit.manifest.json
└── scripts/
    └── bash/                    # helper shell scripts
```

## The constitution

`memory/constitution.md` is the authoritative statement of non-negotiable
architecture principles. Every implementation plan (`specs/*/plan.md`,
`docs/superpowers/plans/*.md`) cites the constitution in a
"Constitution Check" section. The seven principles are:

1. **Container-First Architecture** — two containers + one host bridge.
2. **Plugin Contract Integrity** — nova3 plugin contract.
3. **Credential & Secret Security** — layered env loading, no secrets
   in VCS.
4. **Container Runtime Portability** — podman preferred, docker
   supported.
5. **Private Tracker Bridge Pattern** — `webui-bridge.py` path.
6. **Validation-Driven Development** — TDD + rebuild-reboot.
7. **Operational Simplicity** — one-shot lifecycle scripts.

Plus three supporting sections: **Security Requirements**,
**Development Workflow & Quality Gates**, **Governance**.

The current version is tracked in the document header; bumps follow
SemVer and update the Sync Impact Report at the top of the file.

## Templates

`templates/` holds the boilerplate the `superpowers:writing-plans` and
`superpowers:executing-plans` skills copy into a new feature directory
under `specs/NNN-feature-name/`. Do not edit templates from a feature
directory — edit them here so all future specs inherit the change.

## Extensions & integrations

- `extensions/` — per-extension config (git extension is the only one
  populated today).
- `integrations/` — manifests for every harness that can drive
  GitSpec (OpenCode, SpecKit). Each harness declares its slash-command
  surface in its manifest so `init-options.json` knows which commands
  to expose.

## Scripts

`scripts/bash/` contains helper shell scripts invoked by the GitSpec
harness (e.g. `new-feature.sh` to scaffold a new `specs/NNN-*/`
directory). They are intentionally shell-only so they are portable
across environments without a Python runtime.

## Conventions

- All files are plain text — Markdown, JSON, YAML, shell.
- Do not hand-edit `feature.json` mid-work; the harness owns it.
- When updating the constitution, bump the version in the top-of-file
  Sync Impact Report and run every dependent plan through the
  Constitution Check step again.
- `integration.json` is merged with any user-level config; keep it
  minimal so users can override in `~/.specify/`.

## Tests

No dedicated tests for this directory. The constitution is enforced by
code reviews and by the tests in `tests/unit/test_no_runtime_service_skips.py`,
`tests/unit/test_toolchain_config.py`, `tests/unit/test_ci_workflows.py`
(each of which encodes one or more constitution principles).

## Gotchas

- The `memory/constitution.md` file is **the** project constitution —
  never check in a second copy. If a doc needs to quote it, reference
  it with a relative link.
- `feature.json` changes between branches; do not cherry-pick it.
- OpenCode and Claude Code harnesses read this directory at session
  start. Edit-in-flight inconsistencies (e.g. deleting a template
  while a plan is executing) will surface as confusing errors from
  the skills, not from this tooling.
