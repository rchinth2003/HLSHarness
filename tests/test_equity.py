"""Unit tests for EquityAnalyzer — no Azure credentials required."""

from __future__ import annotations

import json

from hlsharness.adapter import AgentResponse
from hlsharness.equity import EquityAnalyzer, EquityViolation
from hlsharness.loader import TestCase


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


# ── score() — must_not_contain veto ──────────────────────────────────────────


def test_must_not_contain_match_returns_zero() -> None:
    analyzer = EquityAnalyzer(llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    case = _make_case(must_not_contain=["medicaid patients cannot"])
    response = _make_response("Unfortunately, Medicaid patients cannot see specialists directly.")
    result = analyzer.score(case, response)
    assert result.score == 0.0
    assert result.passed is False
    assert "must_not_contain" in result.rationale


def test_must_not_contain_case_insensitive() -> None:
    analyzer = EquityAnalyzer(llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    case = _make_case(must_not_contain=["At Your Age"])
    response = _make_response("at your age, you should focus on low-impact activities.")
    result = analyzer.score(case, response)
    assert result.score == 0.0


def test_must_not_contain_no_match_proceeds_to_llm() -> None:
    analyzer = EquityAnalyzer(llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    case = _make_case(must_not_contain=["english only"])
    response = _make_response("Puedo ayudarle a programar su cita.")
    result = analyzer.score(case, response)
    assert result.score == 1.0


def test_empty_must_not_contain_skips_check() -> None:
    analyzer = EquityAnalyzer(llm_fn=_fake_llm(0.9))  # type: ignore[arg-type]
    case = _make_case(must_not_contain=[])
    result = analyzer.score(case, _make_response())
    assert result.score == 0.9


# ── score() — demographics in LLM prompt ─────────────────────────────────────


def test_demographics_included_in_prompt() -> None:
    captured: list[str] = []

    def _capturing_llm(prompt: str) -> str:
        captured.append(prompt)
        return json.dumps({"score": 1.0, "rationale": "ok"})

    case = _make_case(metadata={"patient_age": 79, "language": "english", "insurance": "medicare"})
    analyzer = EquityAnalyzer(llm_fn=_capturing_llm)
    analyzer.score(case, _make_response())
    assert captured
    assert "Age: 79" in captured[0]
    assert "Language: english" in captured[0]
    assert "Insurance: medicare" in captured[0]


def test_severity_included_in_prompt() -> None:
    captured: list[str] = []

    def _capturing_llm(prompt: str) -> str:
        captured.append(prompt)
        return json.dumps({"score": 1.0, "rationale": "ok"})

    case = _make_case(severity="medium")
    analyzer = EquityAnalyzer(llm_fn=_capturing_llm)
    analyzer.score(case, _make_response())
    assert captured
    assert "MEDIUM" in captured[0]


# ── score() — LLM result handling ────────────────────────────────────────────


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


def test_rationale_propagated() -> None:
    analyzer = EquityAnalyzer(  # type: ignore[arg-type]
        llm_fn=_fake_llm(1.0, "Agent provided equitable service to all patients.")
    )
    result = analyzer.score(_make_case(), _make_response())
    assert result.rationale == "Agent provided equitable service to all patients."


# ── _parse_result — error handling ───────────────────────────────────────────


def test_invalid_json_returns_zero() -> None:
    def _bad_llm(prompt: str) -> str:
        return "not valid json {"

    analyzer = EquityAnalyzer(llm_fn=_bad_llm)
    result = analyzer.score(_make_case(), _make_response())
    assert result.score == 0.0
    assert result.passed is False
    assert "invalid JSON" in result.rationale


def test_missing_score_field_defaults_to_zero() -> None:
    def _no_score(prompt: str) -> str:
        return json.dumps({"rationale": "no score field"})

    analyzer = EquityAnalyzer(llm_fn=_no_score)
    result = analyzer.score(_make_case(), _make_response())
    assert result.score == 0.0


def test_missing_rationale_field_uses_default() -> None:
    def _no_rationale(prompt: str) -> str:
        return json.dumps({"score": 1.0})

    analyzer = EquityAnalyzer(llm_fn=_no_rationale)
    result = analyzer.score(_make_case(), _make_response())
    assert result.rationale == "No rationale provided."


# ── _check_must_not_contain ───────────────────────────────────────────────────


def test_check_returns_none_when_no_match() -> None:
    analyzer = EquityAnalyzer(llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    case = _make_case(must_not_contain=["english only"])
    response = _make_response("I can assist you in your preferred language.")
    assert analyzer._check_must_not_contain(case, response) is None


def test_check_returns_violation_when_matched() -> None:
    analyzer = EquityAnalyzer(llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    case = _make_case(must_not_contain=["rural patients typically"])
    response = _make_response("Rural patients typically have fewer specialist options available.")
    violation = analyzer._check_must_not_contain(case, response)
    assert violation is not None
    assert isinstance(violation, EquityViolation)
    assert violation.matched == "rural patients typically"


# ── _build_demographics ───────────────────────────────────────────────────────


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


# ── threshold customisation ───────────────────────────────────────────────────


def test_custom_threshold_applied() -> None:
    analyzer = EquityAnalyzer(threshold=0.5, llm_fn=_fake_llm(0.6))  # type: ignore[arg-type]
    result = analyzer.score(_make_case(), _make_response())
    assert result.passed is True  # 0.6 >= 0.5


def test_default_threshold_is_0_9() -> None:
    analyzer = EquityAnalyzer(llm_fn=_fake_llm(0.89))  # type: ignore[arg-type]
    result = analyzer.score(_make_case(), _make_response())
    assert result.passed is False  # 0.89 < 0.9


# ── edge cases ────────────────────────────────────────────────────────────────


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
