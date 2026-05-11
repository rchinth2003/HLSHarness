"""Unit tests for dashboard.loader — no Streamlit import required."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dashboard.loader import DashResults, DashSolutionResult, load_results, load_solution_results


def _write_results(tmp_path: Path, overrides: dict[str, object] | None = None) -> Path:
    base: dict[str, object] = {
        "agent": "scheduling-v1",
        "run_at": "2026-05-10T05:00:00+00:00",
        "passed": True,
        "categories": [
            {
                "category": "functional",
                "total": 2,
                "passed_count": 2,
                "pass_rate": 1.0,
                "threshold": 0.8,
                "met_threshold": True,
            }
        ],
        "cases": [
            {
                "case_id": "TC-001",
                "agent": "scheduling-v1",
                "category": "functional",
                "input_summary": "Book an appointment",
                "score": 0.9,
                "passed": True,
                "rationale": "Correct booking confirmed",
                "trajectory": [{"tool": "book_appointment", "args": {}, "response": "OK"}],
                "latency_ms": 1200.5,
                "prompt_tokens": 300,
                "completion_tokens": 80,
                "metadata": {"language": "english"},
            },
            {
                "case_id": "TC-002",
                "agent": "scheduling-v1",
                "category": "functional",
                "input_summary": "Cancel appointment",
                "score": 0.85,
                "passed": True,
                "rationale": "Cancellation confirmed",
                "trajectory": [],
                "latency_ms": 900.0,
                "prompt_tokens": 250,
                "completion_tokens": 60,
                "metadata": {},
            },
        ],
    }
    if overrides:
        base.update(overrides)
    out = tmp_path / "results.json"
    out.write_text(json.dumps(base), encoding="utf-8")
    return out


def test_load_returns_dash_results(tmp_path: Path) -> None:
    path = _write_results(tmp_path)
    results = load_results(path)
    assert isinstance(results, DashResults)
    assert results.agent == "scheduling-v1"
    assert results.passed is True


def test_load_categories(tmp_path: Path) -> None:
    results = load_results(_write_results(tmp_path))
    assert len(results.categories) == 1
    cat = results.categories[0]
    assert cat.category == "functional"
    assert cat.total == 2
    assert cat.passed_count == 2
    assert cat.pass_rate == 1.0
    assert cat.threshold == 0.8
    assert cat.met_threshold is True


def test_load_cases(tmp_path: Path) -> None:
    results = load_results(_write_results(tmp_path))
    assert len(results.cases) == 2
    case = results.cases[0]
    assert case.case_id == "TC-001"
    assert case.score == 0.9
    assert case.passed is True
    assert case.latency_ms == 1200.5
    assert case.prompt_tokens == 300
    assert case.completion_tokens == 80


def test_total_tokens_property(tmp_path: Path) -> None:
    results = load_results(_write_results(tmp_path))
    assert results.cases[0].total_tokens == 380
    assert results.total_tokens == 380 + 310


def test_avg_latency(tmp_path: Path) -> None:
    results = load_results(_write_results(tmp_path))
    assert results.avg_latency_ms == pytest.approx((1200.5 + 900.0) / 2, abs=0.01)


def test_overall_pass_rate(tmp_path: Path) -> None:
    results = load_results(_write_results(tmp_path))
    assert results.overall_pass_rate == 1.0


def test_total_cases_and_passed(tmp_path: Path) -> None:
    results = load_results(_write_results(tmp_path))
    assert results.total_cases == 2
    assert results.total_passed == 2


def test_cases_for_category(tmp_path: Path) -> None:
    results = load_results(_write_results(tmp_path))
    assert len(results.cases_for_category("functional")) == 2
    assert results.cases_for_category("safety") == []


def test_failed_count_property(tmp_path: Path) -> None:
    results = load_results(_write_results(tmp_path))
    assert results.categories[0].failed_count == 0


def test_trajectory_loaded(tmp_path: Path) -> None:
    results = load_results(_write_results(tmp_path))
    assert results.cases[0].trajectory == [
        {"tool": "book_appointment", "args": {}, "response": "OK"}
    ]


def test_metadata_loaded(tmp_path: Path) -> None:
    results = load_results(_write_results(tmp_path))
    assert results.cases[0].metadata.get("language") == "english"


def test_file_not_found_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_results(tmp_path / "nonexistent.json")


def test_missing_key_raises(tmp_path: Path) -> None:
    path = _write_results(tmp_path, overrides={"passed": None})
    # 'passed' is present but None — load still works (it's a value override)
    # test with a truly missing key
    raw = json.loads(path.read_text())
    del raw["agent"]
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="missing required key"):
        load_results(path)


def test_avg_latency_empty() -> None:
    results = DashResults(
        agent="x",
        run_at="2026-01-01T00:00:00Z",
        passed=True,
        categories=[],
        cases=[],
    )
    assert results.avg_latency_ms == 0.0


def test_overall_pass_rate_empty() -> None:
    results = DashResults(
        agent="x",
        run_at="2026-01-01T00:00:00Z",
        passed=True,
        categories=[],
        cases=[],
    )
    assert results.overall_pass_rate == 0.0


# ── load_solution_results ─────────────────────────────────────────────────────


def _write_solution_results(tmp_path: Path, overrides: dict[str, object] | None = None) -> Path:
    base: dict[str, object] = {
        "solution": "prior-auth-v1",
        "run_at": "2026-05-10T05:00:00+00:00",
        "passed": True,
        "solution_categories": [
            {
                "category": "functional",
                "total": 4,
                "passed_count": 4,
                "pass_rate": 1.0,
                "threshold": 0.8,
                "met_threshold": True,
            }
        ],
        "agent_results": [
            {
                "agent": "scheduling-v1",
                "run_at": "2026-05-10T05:00:00+00:00",
                "passed": True,
                "categories": [
                    {
                        "category": "functional",
                        "total": 2,
                        "passed_count": 2,
                        "pass_rate": 1.0,
                        "threshold": 0.8,
                        "met_threshold": True,
                    }
                ],
                "cases": [],
            },
            {
                "agent": "billing-v1",
                "run_at": "2026-05-10T05:00:00+00:00",
                "passed": False,
                "categories": [
                    {
                        "category": "functional",
                        "total": 2,
                        "passed_count": 1,
                        "pass_rate": 0.5,
                        "threshold": 0.8,
                        "met_threshold": False,
                    }
                ],
                "cases": [],
            },
        ],
    }
    if overrides:
        base.update(overrides)
    out = tmp_path / "solution_results.json"
    out.write_text(json.dumps(base), encoding="utf-8")
    return out


def test_load_solution_results_returns_correct_type(tmp_path: Path) -> None:
    sol = load_solution_results(_write_solution_results(tmp_path))
    assert isinstance(sol, DashSolutionResult)
    assert sol.solution == "prior-auth-v1"
    assert sol.passed is True


def test_load_solution_results_solution_categories(tmp_path: Path) -> None:
    sol = load_solution_results(_write_solution_results(tmp_path))
    assert len(sol.solution_categories) == 1
    cat = sol.solution_categories[0]
    assert cat.category == "functional"
    assert cat.pass_rate == 1.0
    assert cat.met_threshold is True


def test_load_solution_results_agent_rollups_count(tmp_path: Path) -> None:
    sol = load_solution_results(_write_solution_results(tmp_path))
    assert len(sol.agent_rollups) == 2
    agents = [ar.agent for ar in sol.agent_rollups]
    assert "scheduling-v1" in agents
    assert "billing-v1" in agents


def test_load_solution_results_agent_rollup_categories(tmp_path: Path) -> None:
    sol = load_solution_results(_write_solution_results(tmp_path))
    billing = next(ar for ar in sol.agent_rollups if ar.agent == "billing-v1")
    assert billing.passed is False
    assert billing.categories[0].pass_rate == pytest.approx(0.5)
    assert billing.categories[0].met_threshold is False


def test_load_solution_results_missing_key_raises(tmp_path: Path) -> None:
    path = _write_solution_results(tmp_path)
    raw = json.loads(path.read_text())
    del raw["solution"]
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="missing required key"):
        load_solution_results(path)


def test_load_solution_results_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_solution_results(tmp_path / "nonexistent.json")
