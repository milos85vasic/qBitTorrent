# Disabled GitHub Actions workflows

These YAMLs are intentionally **not** under `.github/workflows/` so
GitHub Actions ignores them.

They were disabled by the project owner; see the commit that moved
them here for the decision. To re-enable:

```bash
git mv .github/workflows-disabled .github/workflows
# commit + push
```

Each file is otherwise a valid workflow (validated by
`tests/unit/test_ci_workflows.py`).
