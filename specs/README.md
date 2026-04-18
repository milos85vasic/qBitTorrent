# specs/ — GitSpec Feature Specifications

This directory holds every numbered feature specification for the
qBittorrent-Fixed project. The layout is the one defined by GitSpec
and the `.specify/` tooling — each feature gets its own directory
prefixed with a zero-padded number.

## Current specs

| Directory | Feature |
|---|---|
| `001-merge-search-trackers/` | Merge Search Service across RuTracker, Kinozal, NNMClub (+ public trackers) |

Each feature directory contains:

```
001-merge-search-trackers/
├── spec.md          # user-facing requirements and acceptance criteria
├── plan.md          # technical implementation plan
├── tasks.md         # checkbox-tracked task list
├── data-model.md    # schemas + field meanings (if applicable)
├── quickstart.md    # walk-through for reviewers
├── contracts/       # API / schema / interface contracts
└── checklists/      # pre-merge and post-merge review checklists
```

## How to create a new spec

GitSpec provides a one-shot command:

```bash
# From the repo root
.specify/scripts/new-feature.sh "short-feature-name"
# or hand-create:
mkdir -p specs/002-my-feature/{contracts,checklists}
cp .specify/templates/spec-template.md      specs/002-my-feature/spec.md
cp .specify/templates/plan-template.md      specs/002-my-feature/plan.md
cp .specify/templates/tasks-template.md     specs/002-my-feature/tasks.md
cp .specify/templates/checklist-template.md specs/002-my-feature/checklists/pre-merge.md
```

Numbers are assigned in order; gaps are discouraged but allowed. Do
not renumber existing directories — cross-references in commit
messages rely on stable paths.

## Conventions

- **English only**, per the project-wide rule in `AGENTS.md`.
- `spec.md` is end-user language; `plan.md` and `tasks.md` are
  developer language.
- Every `tasks.md` uses `- [ ]` / `- [x]` checkboxes so the
  `superpowers:executing-plans` and `superpowers:subagent-driven-development`
  skills can track progress automatically.
- Plans reference the constitution (`.specify/memory/constitution.md`)
  in a "Constitution Check" section and flag any principle violation
  before coding starts.
- `contracts/` holds frozen JSON / OpenAPI / dataclass definitions —
  they are the contract the tests enforce.

## Relationship to docs/

- `specs/` is **authoritative for features under active development**.
  Once a feature ships, the operational docs move under `docs/` and
  the spec becomes a historical record.
- `docs/superpowers/plans/` is a different tree: it holds
  **cross-feature plans** that span many specs at once (e.g. the
  completion-initiative plan). GitSpec specs are feature-scoped;
  superpowers plans are program-scoped.

## Tests

No dedicated pytest hook yet. When a spec ships with interface
contracts under `contracts/`, a corresponding test should live in
`tests/contract/` to prevent drift.

## Gotchas

- Do not edit the templates in `.specify/templates/` from a spec
  directory. Copy-and-modify; the templates are shared across specs.
- `tasks.md` is machine-read — keep checkbox syntax intact
  (`- [ ]` / `- [x]`, exactly those three characters between the
  brackets).
- Spec numbers are global across branches. If a second branch starts
  spec `002` while yours is in flight, rebase to resolve the
  collision — do not rename either.
