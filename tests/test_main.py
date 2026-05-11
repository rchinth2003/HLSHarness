"""Unit tests for the __main__ CLI argument parser — no Azure credentials required."""

from __future__ import annotations

import dataclasses

import pytest

from hlsharness.__main__ import _apply_baseline_deltas, _build_parser, _compute_exit_code
from hlsharness.results import CategorySummary, EvalResults


def test_default_cases_path() -> None:
    args = _build_parser().parse_args([])
    assert args.cases == "cases"


def test_default_agent() -> None:
    args = _build_parser().parse_args([])
    assert args.agent == "scheduling-v1"


def test_default_out() -> None:
    args = _build_parser().parse_args([])
    assert args.out == "results.json"


def test_custom_cases_path() -> None:
    args = _build_parser().parse_args(["--cases", "/tmp/my-cases"])
    assert args.cases == "/tmp/my-cases"


def test_custom_agent() -> None:
    args = _build_parser().parse_args(["--agent", "prior-auth-v2"])
    assert args.agent == "prior-auth-v2"


def test_custom_out() -> None:
    args = _build_parser().parse_args(["--out", "artifacts/results.json"])
    assert args.out == "artifacts/results.json"


def test_unknown_flag_raises_system_exit() -> None:
    with pytest.raises(SystemExit):
        _build_parser().parse_args(["--unknown-flag"])


# ── new flags (Slice 16D) ─────────────────────────────────────────────────────


def test_baseline_flag_default_false() -> None:
    args = _build_parser().parse_args([])
    assert args.baseline is False


def test_baseline_flag_sets_true() -> None:
    args = _build_parser().parse_args(["--baseline"])
    assert args.baseline is True


def test_db_flag_default() -> None:
    args = _build_parser().parse_args([])
    assert args.db == ".hls_runs.db"


def test_db_flag_custom() -> None:
    args = _build_parser().parse_args(["--db", "/tmp/runs.db"])
    assert args.db == "/tmp/runs.db"


def test_version_flag_default_empty() -> None:
    args = _build_parser().parse_args([])
    assert args.version == ""


def test_version_flag_custom() -> None:
    args = _build_parser().parse_args(["--version", "2.0"])
    assert args.version == "2.0"


# ── _apply_baseline_deltas ────────────────────────────────────────────────────


def _make_cat(category: str, pass_rate: float) -> CategorySummary:
    return CategorySummary(
        category=category,
        total=5,
        passed_count=int(5 * pass_rate),
        pass_rate=pass_rate,
        threshold=0.8,
        met_threshold=pass_rate >= 0.8,
    )


def test_apply_baseline_deltas_positive() -> None:
    current = [_make_cat("functional", 1.0)]
    baseline = [_make_cat("functional", 0.8)]
    result = _apply_baseline_deltas(current, baseline)
    assert result[0].delta_vs_baseline == pytest.approx(0.2)


def test_apply_baseline_deltas_negative() -> None:
    current = [_make_cat("safety", 0.7)]
    baseline = [_make_cat("safety", 0.9)]
    result = _apply_baseline_deltas(current, baseline)
    assert result[0].delta_vs_baseline == pytest.approx(-0.2)


def test_apply_baseline_deltas_zero() -> None:
    current = [_make_cat("functional", 0.8)]
    baseline = [_make_cat("functional", 0.8)]
    result = _apply_baseline_deltas(current, baseline)
    assert result[0].delta_vs_baseline == pytest.approx(0.0)


def test_apply_baseline_deltas_missing_category_stays_none() -> None:
    current = [_make_cat("equity", 0.9)]
    baseline = [_make_cat("functional", 1.0)]
    result = _apply_baseline_deltas(current, baseline)
    assert result[0].delta_vs_baseline is None


def test_apply_baseline_deltas_preserves_other_fields() -> None:
    current = [_make_cat("functional", 1.0)]
    baseline = [_make_cat("functional", 0.9)]
    result = _apply_baseline_deltas(current, baseline)
    assert result[0].category == "functional"
    assert result[0].pass_rate == pytest.approx(1.0)


# ── _compute_exit_code ────────────────────────────────────────────────────────


def _make_results(passed: bool, categories: list[CategorySummary]) -> EvalResults:
    return EvalResults(
        agent="scheduling-v1",
        run_at="2026-05-11T00:00:00+00:00",
        cases=[],
        categories=categories,
        passed=passed,
    )


def test_compute_exit_code_1_when_not_passed() -> None:
    results = _make_results(passed=False, categories=[_make_cat("functional", 0.5)])
    assert _compute_exit_code(results, {}) == 1


def test_compute_exit_code_0_when_passed_no_deltas() -> None:
    results = _make_results(passed=True, categories=[_make_cat("functional", 1.0)])
    assert _compute_exit_code(results, {"functional": 0.1}) == 0


def test_compute_exit_code_0_when_regression_within_threshold() -> None:
    cat = dataclasses.replace(_make_cat("functional", 0.9), delta_vs_baseline=-0.05)
    results = _make_results(passed=True, categories=[cat])
    assert _compute_exit_code(results, {"functional": 0.1}) == 0


def test_compute_exit_code_3_when_regression_exceeds_threshold() -> None:
    cat = dataclasses.replace(_make_cat("functional", 0.7), delta_vs_baseline=-0.2)
    results = _make_results(passed=True, categories=[cat])
    assert _compute_exit_code(results, {"functional": 0.1}) == 3


def test_compute_exit_code_0_when_no_delta_threshold_for_category() -> None:
    cat = dataclasses.replace(_make_cat("functional", 0.7), delta_vs_baseline=-0.5)
    results = _make_results(passed=True, categories=[cat])
    assert _compute_exit_code(results, {}) == 0


def test_compute_exit_code_3_zero_tolerance() -> None:
    cat = dataclasses.replace(_make_cat("safety", 0.9), delta_vs_baseline=-0.01)
    results = _make_results(passed=True, categories=[cat])
    assert _compute_exit_code(results, {"safety": 0.0}) == 3
