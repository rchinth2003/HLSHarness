"""RunStore — SQLite persistence for EvalResults with D1/D2 baseline tagging.

Two baseline strategies coexist:
- D1 (CI auto): baseline = last run where passed=1 and is_baseline=1 for a given
  agent/version. EvalController sets is_baseline=1 automatically on passing runs
  when instructed (e.g. main-branch CI).
- D2 (human promotion): Architect explicitly promotes any run via promote_baseline().
  Clears is_baseline on all prior runs for the same agent/version.

Schema (created on first use):
  runs(id, solution, agent, version, git_sha, run_at, passed, is_baseline)
  category_scores(id, run_id, category, pass_rate, met_threshold, delta_vs_baseline)
"""

from __future__ import annotations

import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path

from hlsharness.results import CategorySummary, EvalResults

_DEFAULT_DB = Path(".hls_runs.db")

_DDL = """
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    solution    TEXT,
    agent       TEXT    NOT NULL,
    version     TEXT    NOT NULL DEFAULT '',
    git_sha     TEXT    NOT NULL DEFAULT '',
    run_at      TEXT    NOT NULL,
    passed      INTEGER NOT NULL DEFAULT 0,
    is_baseline INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS category_scores (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id             INTEGER NOT NULL REFERENCES runs(id),
    category           TEXT    NOT NULL,
    pass_rate          REAL    NOT NULL,
    met_threshold      INTEGER NOT NULL DEFAULT 0,
    delta_vs_baseline  REAL
);
"""


def _git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


@dataclass
class RunRecord:
    """A stored run row with its category scores."""

    id: int
    solution: str | None
    agent: str
    version: str
    git_sha: str
    run_at: str
    passed: bool
    is_baseline: bool
    categories: list[CategorySummary]


class RunStore:
    """Thin SQLite wrapper for persisting EvalResults across runs.

    Parameters
    ----------
    db_path:
        Path to the SQLite database file. Created on first use.
        Defaults to ``.hls_runs.db`` in the working directory.
    """

    def __init__(self, db_path: Path = _DEFAULT_DB) -> None:
        self._db_path = db_path
        self._init_db()

    # ── public interface ──────────────────────────────────────────────────────

    def save(
        self,
        result: EvalResults,
        *,
        solution: str | None = None,
        version: str = "",
        git_sha: str | None = None,
        is_baseline: bool = False,
    ) -> int:
        """Persist an EvalResults run. Returns the auto-incremented run id."""
        sha = git_sha if git_sha is not None else _git_sha()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO runs (solution, agent, version, git_sha, run_at, passed, is_baseline)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    solution,
                    result.agent,
                    version,
                    sha,
                    result.run_at,
                    int(result.passed),
                    int(is_baseline),
                ),
            )
            run_id = cur.lastrowid
            assert run_id is not None
            conn.executemany(
                """
                INSERT INTO category_scores (run_id, category, pass_rate, met_threshold)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (run_id, c.category, c.pass_rate, int(c.met_threshold))
                    for c in result.categories
                ],
            )
        return run_id

    def load_baseline(self, agent: str, version: str = "") -> RunRecord | None:
        """Return the most recent baseline run for agent/version, or None."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, solution, agent, version, git_sha, run_at, passed, is_baseline
                FROM runs
                WHERE agent = ? AND version = ? AND is_baseline = 1
                ORDER BY run_at DESC
                LIMIT 1
                """,
                (agent, version),
            ).fetchone()
            if row is None:
                return None
            return self._to_record(conn, row)

    def promote_baseline(self, run_id: int) -> None:
        """Mark run_id as baseline; clear the flag on all other runs for same agent/version."""
        with self._connect() as conn:
            row = conn.execute("SELECT agent, version FROM runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                raise ValueError(f"RunStore: no run with id={run_id}")
            agent, version = row
            conn.execute(
                "UPDATE runs SET is_baseline = 0 WHERE agent = ? AND version = ?",
                (agent, version),
            )
            conn.execute("UPDATE runs SET is_baseline = 1 WHERE id = ?", (run_id,))

    def history(self, agent: str, limit: int = 50) -> list[RunRecord]:
        """Return runs for agent ordered by run_at descending."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, solution, agent, version, git_sha, run_at, passed, is_baseline
                FROM runs
                WHERE agent = ?
                ORDER BY run_at DESC
                LIMIT ?
                """,
                (agent, limit),
            ).fetchall()
            return [self._to_record(conn, row) for row in rows]

    # ── internals ─────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_DDL)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _to_record(self, conn: sqlite3.Connection, row: sqlite3.Row) -> RunRecord:
        run_id = row["id"]
        score_rows = conn.execute(
            "SELECT category, pass_rate, met_threshold FROM category_scores WHERE run_id = ?",
            (run_id,),
        ).fetchall()
        categories = [
            CategorySummary(
                category=r["category"],
                total=0,
                passed_count=0,
                pass_rate=r["pass_rate"],
                threshold=0.0,
                met_threshold=bool(r["met_threshold"]),
            )
            for r in score_rows
        ]
        return RunRecord(
            id=run_id,
            solution=row["solution"],
            agent=row["agent"],
            version=row["version"],
            git_sha=row["git_sha"],
            run_at=row["run_at"],
            passed=bool(row["passed"]),
            is_baseline=bool(row["is_baseline"]),
            categories=categories,
        )
