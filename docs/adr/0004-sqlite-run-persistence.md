# ADR-0004: SQLite for Run Persistence (RunStore)

**Status:** Accepted  
**Date:** 2026-05-11

## Context

Regression drift detection requires persisting `EvalResults` across runs so that the current run can be compared against a prior baseline. Without persistence, every run is a snapshot — the harness cannot detect whether a score dropped, improved, or held steady between agent versions.

Four storage options were considered:

1. **JSON files on disk** — append a JSON file per run to a `runs/` directory. Simple, no dependencies. Poor for queries: "give me the last passing run for scheduling-v1" requires scanning every file.
2. **SQLite (this decision)** — structured rows, queryable, zero server, stdlib `sqlite3` module. Supports the four `RunStore` operations cleanly.
3. **Azure Cosmos DB / Azure Blob** — hosted, durable, queryable at scale. Requires Azure credentials and network access during eval runs. Adds a cloud dependency to what is otherwise a local CLI tool.
4. **ORM (SQLAlchemy)** — adds a migration framework on top of SQLite. Unnecessary for a two-table schema with four operations.

The Architects using this harness run `hls-eval` locally in CI pipelines. A cloud dependency on the persistence path means eval fails if Azure credentials are unavailable — a violation of the harness's offline-capable design. JSON files lack query semantics needed for baseline selection.

## Decision

Use **SQLite via Python's stdlib `sqlite3`** with no ORM. The `RunStore` module owns schema creation on first use.

Schema:
- `runs(id INTEGER PRIMARY KEY, solution TEXT, agent TEXT, version TEXT, git_sha TEXT, run_at TEXT, passed INTEGER, is_baseline INTEGER)`
- `category_scores(id INTEGER PRIMARY KEY, run_id INTEGER, category TEXT, pass_rate REAL, met_threshold INTEGER, delta_vs_baseline REAL)`

The DB file defaults to `.hls_runs.db` in the working directory; the path is injectable for tests.

Two baseline tagging strategies coexist:
- **D1 (CI auto):** baseline = last run where `passed = 1` and `is_baseline = 1` for a given agent/version. The CI pipeline sets `is_baseline = 1` on a run automatically when it lands on the main branch.
- **D2 (human promotion):** an Architect explicitly promotes any run to baseline via the dashboard. `promote_baseline(run_id)` clears the flag on all prior runs for the same agent/version (only one baseline per agent/version at a time).

## Consequences

- `RunStore` is a stdlib-only dependency. No pip install required.
- Schema migrations are manual if the schema changes. Acceptable: two tables with stable columns for the foreseeable scope.
- The DB file is local; sharing run history across team members requires committing the file or moving to a hosted store. Deferred as out of scope — the Streamlit dashboard reads `RunStore` directly and is single-user today.
- **Trade-off accepted:** SQLite is not suitable for concurrent writes from parallel CI jobs. Accepted because each `hls-eval` run is a sequential process; parallel CI jobs target different DB files (different working directories).
