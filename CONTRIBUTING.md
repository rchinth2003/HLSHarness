# Contributing to HLS Harness

## Branch strategy

Work in a feature branch per slice. Branch names follow the pattern:

```
slice-{number}-{short-description}
# examples
slice-15a-maf-sdk-spike
slice-15b-maf-yaml-eval
```

Never push directly to `main`.

## Opening a pull request

1. Open a draft PR early so CI runs on your branch.
2. Fill the PR description with: what changed, how to verify it, and which issue it closes (`Closes #NN`).
3. Ensure all CI checks are green before marking ready for review:
   - `ruff format --check` — format gate (run `ruff format hlsharness tests` to fix)
   - `ruff check` — lint gate
   - `mypy --strict` — type gate (configured in `pyproject.toml`)
   - `pytest --cov-fail-under=80` — test + coverage gate

## Code review process

Every PR requires **one approving human review** before merge. Branch protection enforces this — no exceptions, including for maintainers.

A **Copilot automated review** is requested automatically when the PR opens. Read the Copilot feedback before requesting human review — address any flagged issues or leave a reply explaining why you disagree.

Review checklist for human reviewers:

- [ ] Behavior matches the slice acceptance criteria in the linked issue
- [ ] Tests assert external behavior only (no patching of internals)
- [ ] No Azure credentials required in any test
- [ ] Coverage gate still passes (`pytest --cov-fail-under=80`)
- [ ] Documentation updated if the change affects Architect or Tool Function Implementer workflows

## Stale approvals

Branch protection dismisses approvals when new commits are pushed. If you push a fix after receiving approval, request re-review before merging.

## Merging

Merge with **squash and merge** so `main` has one commit per slice. The squash commit message should be: `Slice {ID}: {short description} (#{PR number})`.

## Slice sequencing

Do not start a slice until its blockers are merged and CI is green on `main`. The dependency history is recorded in `SLICE_PLAN.md`.

## Local development

```bash
uv sync --all-groups          # install all deps including dev
uv run ruff format hlsharness tests   # auto-format before committing
uv run ruff check hlsharness tests    # lint check
uv run mypy hlsharness                # type check
uv run pytest tests/ -v              # run tests with coverage
```

See `README.md` for full setup instructions including Azure credential configuration.
