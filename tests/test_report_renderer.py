"""Unit tests for ReportRenderer — no weasyprint / Azure required."""

from __future__ import annotations

from hlsharness.report_config import ReportConfig
from hlsharness.report_renderer import ReportRenderer
from hlsharness.results import CaseResult, CategorySummary, EvalResults

# ── fixtures ──────────────────────────────────────────────────────────────────


def _make_results(passed: bool = True) -> EvalResults:
    cases = [
        CaseResult(
            case_id="TC-001",
            agent="prior-auth-v1",
            category="functional",
            input_summary="Can I get prior auth for an MRI?",
            score=0.9,
            passed=True,
            rationale="Agent correctly checked coverage.",
            trajectory=[],
            latency_ms=120.0,
            prompt_tokens=100,
            completion_tokens=50,
        ),
        CaseResult(
            case_id="TC-002",
            agent="prior-auth-v1",
            category="safety",
            input_summary="I need urgent medication approval.",
            score=0.4,
            passed=False,
            rationale="Agent failed to escalate.",
            trajectory=[],
            latency_ms=80.0,
            prompt_tokens=80,
            completion_tokens=30,
        ),
    ]
    categories = [
        CategorySummary(
            category="functional",
            total=1,
            passed_count=1,
            pass_rate=1.0,
            threshold=0.8,
            met_threshold=True,
        ),
        CategorySummary(
            category="safety",
            total=1,
            passed_count=0,
            pass_rate=0.0,
            threshold=0.9,
            met_threshold=False,
        ),
    ]
    return EvalResults(
        agent="prior-auth-v1",
        run_at="2026-05-10T00:00:00+00:00",
        cases=cases,
        categories=categories,
        passed=passed,
    )


# ── _build_html ────────────────────────────────────────────────────────────────


def test_build_html_returns_string() -> None:
    html = ReportRenderer()._build_html(_make_results(), ReportConfig.defaults(), "2026-05-10")
    assert isinstance(html, str)


def test_build_html_contains_agent_name() -> None:
    html = ReportRenderer()._build_html(_make_results(), ReportConfig.defaults(), "2026-05-10")
    assert "prior-auth-v1" in html


def test_build_html_contains_org_name() -> None:
    config = ReportConfig(org="Acme Health", brand_color="#FF0000")
    html = ReportRenderer()._build_html(_make_results(), config, "2026-05-10")
    assert "Acme Health" in html


def test_build_html_contains_brand_color() -> None:
    config = ReportConfig(brand_color="#ABCDEF")
    html = ReportRenderer()._build_html(_make_results(), config, "2026-05-10")
    assert "#ABCDEF" in html


def test_build_html_contains_date() -> None:
    html = ReportRenderer()._build_html(_make_results(), ReportConfig.defaults(), "2026-05-10")
    assert "2026-05-10" in html


def test_build_html_passed_verdict() -> None:
    html = ReportRenderer()._build_html(
        _make_results(passed=True), ReportConfig.defaults(), "2026-05-10"
    )
    assert "PASSED" in html


def test_build_html_failed_verdict() -> None:
    html = ReportRenderer()._build_html(
        _make_results(passed=False), ReportConfig.defaults(), "2026-05-10"
    )
    assert "FAILED" in html


def test_build_html_contains_category_names() -> None:
    html = ReportRenderer()._build_html(_make_results(), ReportConfig.defaults(), "2026-05-10")
    assert "functional" in html
    assert "safety" in html


def test_build_html_contains_case_ids() -> None:
    html = ReportRenderer()._build_html(_make_results(), ReportConfig.defaults(), "2026-05-10")
    assert "TC-001" in html
    assert "TC-002" in html


def test_build_html_contains_failed_rationale() -> None:
    html = ReportRenderer()._build_html(_make_results(), ReportConfig.defaults(), "2026-05-10")
    assert "Agent failed to escalate." in html


def test_build_html_contains_input_summary() -> None:
    html = ReportRenderer()._build_html(_make_results(), ReportConfig.defaults(), "2026-05-10")
    assert "Can I get prior auth for an MRI?" in html


def test_build_html_no_failed_section_when_all_pass() -> None:
    results = _make_results()
    for c in results.cases:
        c.passed = True
    html = ReportRenderer()._build_html(results, ReportConfig.defaults(), "2026-05-10")
    assert "Failed Cases" not in html


def test_build_html_no_passing_section_when_all_fail() -> None:
    results = _make_results()
    for c in results.cases:
        c.passed = False
    html = ReportRenderer()._build_html(results, ReportConfig.defaults(), "2026-05-10")
    assert "Passing Cases" not in html


def test_build_html_gate_pass_and_fail_present() -> None:
    html = ReportRenderer()._build_html(_make_results(), ReportConfig.defaults(), "2026-05-10")
    assert "PASS" in html
    assert "FAIL" in html


def test_pdf_flag_default_none() -> None:
    from hlsharness.__main__ import _build_parser

    args = _build_parser().parse_args([])
    assert args.pdf is None


def test_pdf_flag_sets_path() -> None:
    from hlsharness.__main__ import _build_parser

    args = _build_parser().parse_args(["--pdf", "out/report.pdf"])
    assert args.pdf == "out/report.pdf"


# ── delta column (Slice 16D) ───────────────────────────────────────────────────


def _make_results_with_delta(delta: float | None) -> EvalResults:
    import dataclasses

    results = _make_results()
    results = dataclasses.replace(
        results,
        categories=[
            dataclasses.replace(results.categories[0], delta_vs_baseline=delta),
            results.categories[1],
        ],
    )
    return results


def test_scorecard_no_delta_column_without_baseline() -> None:
    html = ReportRenderer()._build_html(_make_results(), ReportConfig.defaults(), "2026-05-10")
    assert "<th>Delta</th>" not in html


def test_scorecard_delta_column_present_with_baseline() -> None:
    results = _make_results_with_delta(0.1)
    html = ReportRenderer()._build_html(results, ReportConfig.defaults(), "2026-05-10")
    assert "<th>Delta</th>" in html


def test_scorecard_positive_delta_shown_green() -> None:
    results = _make_results_with_delta(0.1)
    html = ReportRenderer()._build_html(results, ReportConfig.defaults(), "2026-05-10")
    assert "#16a34a" in html
    assert "+10%" in html


def test_scorecard_negative_delta_shown_red() -> None:
    results = _make_results_with_delta(-0.1)
    html = ReportRenderer()._build_html(results, ReportConfig.defaults(), "2026-05-10")
    assert "#dc2626" in html
    assert "-10%" in html


def test_scorecard_none_delta_shows_dash() -> None:
    import dataclasses

    results = _make_results()
    results = dataclasses.replace(
        results,
        categories=[
            dataclasses.replace(results.categories[0], delta_vs_baseline=0.05),
            results.categories[1],
        ],
    )
    html = ReportRenderer()._build_html(results, ReportConfig.defaults(), "2026-05-10")
    assert "<td>—</td>" in html


# ── baseline note ─────────────────────────────────────────────────────────────


def test_baseline_note_absent_by_default() -> None:
    html = ReportRenderer()._build_html(_make_results(), ReportConfig.defaults(), "2026-05-10")
    assert "baseline-note" not in html


def test_baseline_note_present_when_provided() -> None:
    html = ReportRenderer()._build_html(
        _make_results(),
        ReportConfig.defaults(),
        "2026-05-10",
        baseline_note="No baseline found — this run establishes the new baseline.",
    )
    assert "No baseline found" in html
    assert "baseline-note" in html
