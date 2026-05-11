"""Dashboard data loader — pure Python, no Streamlit import.

Reads a ``results.json`` produced by ``EvalController`` and exposes
strongly-typed views used by both the Streamlit UI and unit tests.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DashCaseSummary:
    case_id: str
    category: str
    input_summary: str
    score: float
    passed: bool
    rationale: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    metadata: dict[str, object] = field(default_factory=dict)
    trajectory: list[dict[str, object]] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class DashCategorySummary:
    category: str
    total: int
    passed_count: int
    pass_rate: float
    threshold: float
    met_threshold: bool

    @property
    def failed_count(self) -> int:
        return self.total - self.passed_count


@dataclass
class DashResults:
    agent: str
    run_at: str
    passed: bool
    categories: list[DashCategorySummary]
    cases: list[DashCaseSummary]

    @property
    def total_cases(self) -> int:
        return len(self.cases)

    @property
    def total_passed(self) -> int:
        return sum(1 for c in self.cases if c.passed)

    @property
    def overall_pass_rate(self) -> float:
        return self.total_passed / self.total_cases if self.total_cases else 0.0

    @property
    def avg_latency_ms(self) -> float:
        if not self.cases:
            return 0.0
        return sum(c.latency_ms for c in self.cases) / len(self.cases)

    @property
    def total_tokens(self) -> int:
        return sum(c.total_tokens for c in self.cases)

    def cases_for_category(self, category: str) -> list[DashCaseSummary]:
        return [c for c in self.cases if c.category == category]


@dataclass
class DashAgentRollup:
    agent: str
    categories: list[DashCategorySummary]
    passed: bool


@dataclass
class DashSolutionResult:
    solution: str
    run_at: str
    passed: bool
    solution_categories: list[DashCategorySummary]
    agent_rollups: list[DashAgentRollup]


def load_results(path: Path) -> DashResults:
    """Parse a ``results.json`` file into a ``DashResults`` object.

    Parameters
    ----------
    path:
        Path to the JSON file produced by ``EvalResults.write_json()``.

    Returns
    -------
    DashResults
        Fully populated results object ready for the dashboard.

    Raises
    ------
    FileNotFoundError
        If the path does not exist.
    ValueError
        If the JSON is missing required top-level keys.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))

    for key in ("agent", "run_at", "passed", "categories", "cases"):
        if key not in raw:
            raise ValueError(f"results.json missing required key: '{key}'")

    categories = [
        DashCategorySummary(
            category=c["category"],
            total=c["total"],
            passed_count=c["passed_count"],
            pass_rate=c["pass_rate"],
            threshold=c["threshold"],
            met_threshold=c["met_threshold"],
        )
        for c in raw["categories"]
    ]

    cases = [
        DashCaseSummary(
            case_id=c["case_id"],
            category=c["category"],
            input_summary=c.get("input_summary", ""),
            score=c["score"],
            passed=c["passed"],
            rationale=c.get("rationale", ""),
            latency_ms=c.get("latency_ms", 0.0),
            prompt_tokens=c.get("prompt_tokens", 0),
            completion_tokens=c.get("completion_tokens", 0),
            metadata=c.get("metadata", {}),
            trajectory=c.get("trajectory", []),
        )
        for c in raw["cases"]
    ]

    return DashResults(
        agent=raw["agent"],
        run_at=raw["run_at"],
        passed=raw["passed"],
        categories=categories,
        cases=cases,
    )


def _parse_dash_categories(cats_raw: list[dict[str, object]]) -> list[DashCategorySummary]:
    return [
        DashCategorySummary(
            category=c["category"],
            total=c["total"],
            passed_count=c["passed_count"],
            pass_rate=c["pass_rate"],
            threshold=c["threshold"],
            met_threshold=c["met_threshold"],
        )
        for c in cats_raw
    ]


def load_solution_results(path: Path) -> DashSolutionResult:
    """Parse a ``solution_results.json`` file into a ``DashSolutionResult``.

    Raises
    ------
    FileNotFoundError
        If the path does not exist.
    ValueError
        If the JSON is missing required top-level keys.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))

    for key in ("solution", "run_at", "passed", "solution_categories", "agent_results"):
        if key not in raw:
            raise ValueError(f"solution_results.json missing required key: '{key}'")

    solution_categories = _parse_dash_categories(raw["solution_categories"])
    agent_rollups = [
        DashAgentRollup(
            agent=ar["agent"],
            categories=_parse_dash_categories(ar["categories"]),
            passed=ar["passed"],
        )
        for ar in raw["agent_results"]
    ]

    return DashSolutionResult(
        solution=raw["solution"],
        run_at=raw["run_at"],
        passed=raw["passed"],
        solution_categories=solution_categories,
        agent_rollups=agent_rollups,
    )
