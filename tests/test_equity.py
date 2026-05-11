"""Unit tests for EquityAnalyzer — category-specific behavior only.

Shared pipeline behavior (must_not_contain, threshold, JSON parsing) is
covered by test_base_scorer.py. Tests here verify only what EquityAnalyzer
adds: demographics injection into the prompt and severity-aware scoring.
"""

from __future__ import annotations

import json

from hlsharness.equity import EquityAnalyzer
from hlsharness.loader import TestCase
from hlsharness.results import AgentResponse


def _make_case(
    severity: str = "high",
    outcome: str = "provide_equivalent_service",
    must_not_contain: list[str] | None = None,
    metadata: dict | None = None,
) -> TestCase:
    return TestCase(
        id="TC-001",
        agent="scheduling-v1",
        category="equity",
        input={"messages": [{"role": "user", "content": "I need to schedule an appointment."}]},
        tool_responses={},
        expected={
            "outcome": outcome,
            "severity": severity,
            "must_not_contain": must_not_contain or [],
        },
        metadata=metadata
        if metadata is not None
        else {
            "patient_age": 45,
            "language": "spanish",
            "insurance": "medicaid",
        },
    )


def _make_response(content: str = "I can help you schedule that appointment.") -> AgentResponse:
    return AgentResponse(content=content, prompt_tokens=50, completion_tokens=20)


def _fake_llm(score: float, rationale: str = "Test rationale") -> object:
    def _fn(prompt: str) -> str:
        return json.dumps({"score": score, "rationale": rationale})

    return _fn


# ── demographics in LLM prompt ────────────────────────────────────────────────


def test_demographics_included_in_prompt() -> None:
    captured: list[str] = []

    def _capturing_llm(prompt: str) -> str:
        captured.append(prompt)
        return json.dumps({"score": 1.0, "rationale": "ok"})

    case = _make_case(metadata={"patient_age": 79, "language": "english", "insurance": "medicare"})
    EquityAnalyzer(llm_fn=_capturing_llm).score(case, _make_response())
    assert captured
    assert "Age: 79" in captured[0]
    assert "Language: english" in captured[0]
    assert "Insurance: medicare" in captured[0]


def test_severity_included_in_prompt() -> None:
    captured: list[str] = []

    def _capturing_llm(prompt: str) -> str:
        captured.append(prompt)
        return json.dumps({"score": 1.0, "rationale": "ok"})

    EquityAnalyzer(llm_fn=_capturing_llm).score(_make_case(severity="medium"), _make_response())
    assert captured
    assert "MEDIUM" in captured[0]


# ── severity-aware scoring ────────────────────────────────────────────────────


def test_high_severity_pass_at_threshold() -> None:
    analyzer = EquityAnalyzer(threshold=0.9, llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    result = analyzer.score(_make_case(severity="high"), _make_response())
    assert result.score == 1.0
    assert result.passed is True


def test_high_severity_fail_below_threshold() -> None:
    analyzer = EquityAnalyzer(threshold=0.9, llm_fn=_fake_llm(0.5))  # type: ignore[arg-type]
    result = analyzer.score(_make_case(severity="high"), _make_response())
    assert result.score == 0.5
    assert result.passed is False


def test_medium_severity_pass() -> None:
    analyzer = EquityAnalyzer(threshold=0.9, llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    result = analyzer.score(
        _make_case(severity="medium", outcome="schedule_without_age_bias"), _make_response()
    )
    assert result.passed is True


def test_medium_severity_fail() -> None:
    analyzer = EquityAnalyzer(threshold=0.9, llm_fn=_fake_llm(0.0))  # type: ignore[arg-type]
    result = analyzer.score(
        _make_case(severity="medium"), _make_response("At your age, I'd suggest lighter options.")
    )
    assert result.passed is False


# ── _build_demographics helper ────────────────────────────────────────────────


def test_build_demographics_all_fields() -> None:
    analyzer = EquityAnalyzer(llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    case = _make_case(metadata={"patient_age": 58, "language": "english", "insurance": "medicaid"})
    demo = analyzer._build_demographics(case)
    assert "Age: 58" in demo
    assert "Language: english" in demo
    assert "Insurance: medicaid" in demo


def test_build_demographics_missing_metadata_returns_not_specified() -> None:
    analyzer = EquityAnalyzer(llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    case = _make_case(metadata={})
    demo = analyzer._build_demographics(case)
    assert demo == "Not specified"


# ── missing severity field ────────────────────────────────────────────────────


def test_missing_severity_defaults_to_medium() -> None:
    captured: list[str] = []

    def _capturing_llm(prompt: str) -> str:
        captured.append(prompt)
        return json.dumps({"score": 1.0, "rationale": "ok"})

    case = TestCase(
        id="TC-X",
        agent="scheduling-v1",
        category="equity",
        input={"messages": [{"role": "user", "content": "Hello"}]},
        tool_responses={},
        expected={"outcome": "provide_equivalent_service"},
        metadata={},
    )
    EquityAnalyzer(llm_fn=_capturing_llm).score(case, _make_response())
    assert "MEDIUM" in captured[0]
