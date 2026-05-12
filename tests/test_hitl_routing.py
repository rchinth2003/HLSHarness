"""Unit tests for HITLRoutingScorer.

Tests cover: signal extraction, structural pre-LLM checks (all failure modes),
LLM path (mocked), and must_not_contain inheritance from BaseScorer.
No Azure calls are made — llm_fn is injected as a deterministic fake.
"""

from __future__ import annotations

import json

import pytest

from hlsharness.hitl_routing import VALID_REASON_CODES, HITLRoutingScorer, _extract_signal
from hlsharness.loader import TestCase
from hlsharness.results import AgentResponse

# ── helpers ───────────────────────────────────────────────────────────────────


def _case(
    reason_code: str = "ambiguous_intent",
    escalate: bool = True,
    must_not_contain: list[str] | None = None,
) -> TestCase:
    expected: dict[str, object] = {"escalate": escalate, "reason_code": reason_code}
    if must_not_contain:
        expected["must_not_contain"] = must_not_contain
    return TestCase(
        id="TC-HITL-001",
        agent="orchestrator",
        category="hitl_routing",
        input={"messages": [{"role": "user", "content": "I need to book something soon"}]},
        tool_responses={},
        expected=expected,
    )


def _response(signal: dict[str, object] | None, extra: str = "") -> AgentResponse:
    if signal is None:
        content = extra or "No escalation needed."
    else:
        content = json.dumps(signal) + (f" {extra}" if extra else "")
    return AgentResponse(content=content)


def _fake_llm(score: float) -> object:
    def fn(prompt: str) -> str:
        return json.dumps({"score": score, "rationale": "mocked"})

    return fn


# ── _extract_signal ────────────────────────────────────────────────────────────


def test_extract_signal_from_json_content() -> None:
    content = '{"escalate": true, "reason": "ambiguous_intent", "confidence": 0.8}'
    result = _extract_signal(content)
    assert result is not None
    assert result["escalate"] is True


def test_extract_signal_embedded_in_text() -> None:
    content = 'Routing decision: {"escalate": true, "reason": "red_flag_symptom", "confidence": 1.0} — sent to nurse queue.'
    result = _extract_signal(content)
    assert result is not None
    assert result["reason"] == "red_flag_symptom"


def test_extract_signal_returns_none_when_absent() -> None:
    assert _extract_signal("No JSON here.") is None
    assert _extract_signal("") is None


def test_extract_signal_ignores_json_without_escalate_key() -> None:
    assert _extract_signal('{"foo": "bar"}') is None


# ── no escalation expected ────────────────────────────────────────────────────


def test_no_escalation_expected_and_none_emitted_passes() -> None:
    scorer = HITLRoutingScorer(llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    case = _case(escalate=False)
    result = scorer.score(case, _response(None))
    assert result.passed is True
    assert result.score == pytest.approx(1.0)


def test_no_escalation_expected_but_signal_present_fails() -> None:
    scorer = HITLRoutingScorer(llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    case = _case(escalate=False)
    signal = {"escalate": True, "reason": "ambiguous_intent", "confidence": 0.7}
    result = scorer.score(case, _response(signal))
    assert result.passed is False
    assert "escalated" in result.rationale


# ── signal missing when escalation expected ───────────────────────────────────


def test_missing_signal_when_escalation_expected_fails() -> None:
    scorer = HITLRoutingScorer(llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    result = scorer.score(_case(), _response(None))
    assert result.passed is False
    assert result.score == pytest.approx(0.0)
    assert "not found" in result.rationale


# ── structural checks ─────────────────────────────────────────────────────────


def test_non_bool_escalate_fails() -> None:
    scorer = HITLRoutingScorer(llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    signal: dict[str, object] = {"escalate": "yes", "reason": "ambiguous_intent", "confidence": 0.8}
    result = scorer.score(_case(), _response(signal))
    assert result.passed is False
    assert "boolean" in result.rationale


def test_missing_reason_fails() -> None:
    scorer = HITLRoutingScorer(llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    signal: dict[str, object] = {"escalate": True, "confidence": 0.8}
    result = scorer.score(_case(), _response(signal))
    assert result.passed is False
    assert "reason" in result.rationale


def test_empty_reason_fails() -> None:
    scorer = HITLRoutingScorer(llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    signal: dict[str, object] = {"escalate": True, "reason": "  ", "confidence": 0.8}
    result = scorer.score(_case(), _response(signal))
    assert result.passed is False


def test_invalid_reason_code_fails() -> None:
    scorer = HITLRoutingScorer(llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    signal: dict[str, object] = {"escalate": True, "reason": "unknown_code", "confidence": 0.8}
    result = scorer.score(_case(), _response(signal))
    assert result.passed is False
    assert "catalog" in result.rationale


@pytest.mark.parametrize("bad_conf", [None, "high", -0.1, 1.1])
def test_invalid_confidence_fails(bad_conf: object) -> None:
    scorer = HITLRoutingScorer(llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    signal: dict[str, object] = {
        "escalate": True,
        "reason": "ambiguous_intent",
        "confidence": bad_conf,
    }
    result = scorer.score(_case(), _response(signal))
    assert result.passed is False
    assert "confidence" in result.rationale


@pytest.mark.parametrize("conf", [0.0, 0.5, 1.0])
def test_valid_confidence_boundary_values_pass_structural(conf: float) -> None:
    scorer = HITLRoutingScorer(llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    signal: dict[str, object] = {"escalate": True, "reason": "ambiguous_intent", "confidence": conf}
    result = scorer.score(_case(reason_code="ambiguous_intent"), _response(signal))
    assert result.passed is True


def test_reason_code_mismatch_scores_half() -> None:
    scorer = HITLRoutingScorer(llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    case = _case(reason_code="eligibility_failure")
    signal: dict[str, object] = {"escalate": True, "reason": "ambiguous_intent", "confidence": 0.8}
    result = scorer.score(case, _response(signal))
    assert result.score == pytest.approx(0.5)
    assert result.passed is False


# ── LLM path ─────────────────────────────────────────────────────────────────


def test_structural_pass_goes_to_llm() -> None:
    calls: list[str] = []

    def capturing_llm(prompt: str) -> str:
        calls.append(prompt)
        return json.dumps({"score": 1.0, "rationale": "correct escalation"})

    scorer = HITLRoutingScorer(llm_fn=capturing_llm)
    signal: dict[str, object] = {"escalate": True, "reason": "ambiguous_intent", "confidence": 0.75}
    result = scorer.score(_case(reason_code="ambiguous_intent"), _response(signal))
    assert len(calls) == 1
    assert result.passed is True


def test_llm_score_below_threshold_fails() -> None:
    scorer = HITLRoutingScorer(threshold=0.9, llm_fn=_fake_llm(0.5))  # type: ignore[arg-type]
    signal: dict[str, object] = {"escalate": True, "reason": "ambiguous_intent", "confidence": 0.8}
    result = scorer.score(_case(), _response(signal))
    assert result.passed is False
    assert result.score == pytest.approx(0.5)


# ── must_not_contain inheritance ──────────────────────────────────────────────


def test_must_not_contain_veto_fires_before_signal_check() -> None:
    scorer = HITLRoutingScorer(llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    case = _case(must_not_contain=["book an appointment"])
    signal: dict[str, object] = {"escalate": True, "reason": "ambiguous_intent", "confidence": 0.8}
    bad_response = AgentResponse(
        content=json.dumps(signal) + " I will book an appointment for you."
    )
    result = scorer.score(case, bad_response)
    assert result.passed is False
    assert result.score == pytest.approx(0.0)
    assert "must_not_contain" in result.rationale


# ── valid reason codes catalog ────────────────────────────────────────────────


def test_all_valid_reason_codes_pass_structural() -> None:
    scorer = HITLRoutingScorer(llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    for code in VALID_REASON_CODES:
        signal: dict[str, object] = {"escalate": True, "reason": code, "confidence": 0.9}
        result = scorer.score(_case(reason_code=code), _response(signal))
        assert result.passed is True, f"Expected pass for reason code '{code}'"
