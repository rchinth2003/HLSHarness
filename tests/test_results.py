"""Unit tests for EvalResults serialization — no Azure credentials required."""

import json
from pathlib import Path

from hlsharness.results import CaseResult, CategorySummary, EvalResults


def _make_case(case_id: str = "TC-001", passed: bool = True) -> CaseResult:
    return CaseResult(
        case_id=case_id,
        agent="scheduling-v1",
        category="functional",
        input_summary="Book an appointment",
        score=0.9 if passed else 0.5,
        passed=passed,
        rationale="Test rationale",
        trajectory=[],
        latency_ms=1200.0,
        prompt_tokens=300,
        completion_tokens=80,
    )


def _make_results(passed: bool = True) -> EvalResults:
    cases = [_make_case(passed=passed)]
    categories = [
        CategorySummary(
            category="functional",
            total=1,
            passed_count=1 if passed else 0,
            pass_rate=1.0 if passed else 0.0,
            threshold=0.8,
            met_threshold=passed,
        )
    ]
    return EvalResults.create(agent="scheduling-v1", cases=cases, categories=categories)


def test_passed_reflects_all_categories_met():
    assert _make_results(passed=True).passed is True
    assert _make_results(passed=False).passed is False


def test_to_dict_contains_required_keys():
    d = _make_results().to_dict()
    assert {"agent", "run_at", "passed", "categories", "cases"} <= d.keys()


def test_write_json_creates_file(tmp_path: Path):
    out = tmp_path / "results.json"
    _make_results().write_json(out)
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["agent"] == "scheduling-v1"
    assert isinstance(data["cases"], list)


def test_write_json_creates_parent_directories(tmp_path: Path):
    out = tmp_path / "nested" / "dir" / "results.json"
    _make_results().write_json(out)
    assert out.exists()


def test_run_at_is_iso_timestamp():
    r = _make_results()
    from datetime import datetime

    datetime.fromisoformat(r.run_at)  # raises if invalid
