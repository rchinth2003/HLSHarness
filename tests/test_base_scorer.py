"""Unit tests for BaseScorer — no Azure credentials required.

Uses a _TestScorer stub that implements _build_prompt with a fixed prompt string.
All tests exercise the shared Scoring Pipeline through the public score() interface.
"""

from __future__ import annotations

import json

import pytest

from hlsharness.base_scorer import BaseScorer, MustNotContainViolation
from hlsharness.judge import JudgeResult
from hlsharness.loader import TestCase
from hlsharness.results import AgentResponse

# ── test fixtures ─────────────────────────────────────────────────────────────


class _TestScorer(BaseScorer):
    """Minimal concrete subclass for testing BaseScorer pipeline."""

    PROMPT = "test rubric prompt"

    def _build_prompt(self, case: TestCase, response: AgentResponse) -> str:
        return self.PROMPT


class _PreCheckScorer(BaseScorer):
    """Subclass that overrides _pre_llm_check to return a fixed JudgeResult."""

    def __init__(self, pre_check_result: JudgeResult, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._pre_check_result = pre_check_result

    def _build_prompt(self, case: TestCase, response: AgentResponse) -> str:
        return "pre-check scorer prompt"

    def _pre_llm_check(self, case: TestCase, response: AgentResponse) -> JudgeResult | None:
        return self._pre_check_result


def _make_case(
    must_not_contain: list[str] | None = None,
    outcome: str = "some_outcome",
    severity: str = "high",
    metadata: dict[str, object] | None = None,
) -> TestCase:
    return TestCase(
        id="TC-BASE-001",
        agent="scheduling-v1",
        category="safety",
        input={"messages": [{"role": "user", "content": "Test patient message."}]},
        tool_responses={},
        expected={
            "outcome": outcome,
            "severity": severity,
            "must_not_contain": must_not_contain or [],
        },
        metadata=metadata if metadata is not None else {},
    )


def _make_response(content: str = "Safe response with no violations.") -> AgentResponse:
    return AgentResponse(content=content, prompt_tokens=50, completion_tokens=20)


def _fake_llm(score: float, rationale: str = "Test rationale") -> object:
    def _fn(prompt: str) -> str:
        return json.dumps({"score": score, "rationale": rationale})

    return _fn


# ── must_not_contain veto ─────────────────────────────────────────────────────


def test_must_not_contain_match_returns_zero() -> None:
    scorer = _TestScorer(llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    case = _make_case(must_not_contain=["book an appointment"])
    response = _make_response("I can book an appointment for you at 2pm.")
    result = scorer.score(case, response)
    assert result.score == 0.0
    assert result.passed is False
    assert "book an appointment" in result.rationale


def test_must_not_contain_match_is_case_insensitive() -> None:
    scorer = _TestScorer(llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    case = _make_case(must_not_contain=["BOOK AN APPOINTMENT"])
    response = _make_response("I can book an appointment for you.")
    result = scorer.score(case, response)
    assert result.score == 0.0


def test_must_not_contain_no_match_proceeds_to_llm() -> None:
    scorer = _TestScorer(llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    case = _make_case(must_not_contain=["book an appointment"])
    response = _make_response("Please call 911 immediately.")
    result = scorer.score(case, response)
    assert result.score == 1.0


def test_must_not_contain_empty_list_proceeds_to_llm() -> None:
    scorer = _TestScorer(llm_fn=_fake_llm(0.9))  # type: ignore[arg-type]
    case = _make_case(must_not_contain=[])
    result = scorer.score(case, _make_response())
    assert result.score == 0.9


def test_must_not_contain_short_circuits_before_pre_llm_check() -> None:
    """must_not_contain veto fires before _pre_llm_check."""
    pre_result = JudgeResult(score=0.5, passed=False, rationale="pre-check hit")
    scorer = _PreCheckScorer(pre_check_result=pre_result, llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    case = _make_case(must_not_contain=["forbidden"])
    response = _make_response("forbidden phrase in response")
    result = scorer.score(case, response)
    assert result.score == 0.0
    assert "forbidden" in result.rationale


# ── _pre_llm_check hook ───────────────────────────────────────────────────────


def test_pre_llm_check_default_returns_none_passes_through() -> None:
    """Default _pre_llm_check is a no-op — pipeline reaches the LLM."""
    scorer = _TestScorer(llm_fn=_fake_llm(0.8))  # type: ignore[arg-type]
    result = scorer.score(_make_case(), _make_response())
    assert result.score == 0.8


def test_pre_llm_check_override_short_circuits_llm() -> None:
    """Returning a JudgeResult from _pre_llm_check skips the LLM call entirely."""
    pre_result = JudgeResult(score=0.0, passed=False, rationale="PHI detected")
    llm_called = []

    def _tracking_llm(prompt: str) -> str:
        llm_called.append(prompt)
        return json.dumps({"score": 1.0, "rationale": "should not reach"})

    scorer = _PreCheckScorer(pre_check_result=pre_result, llm_fn=_tracking_llm)
    result = scorer.score(_make_case(), _make_response())

    assert result.score == 0.0
    assert result.rationale == "PHI detected"
    assert llm_called == []


def test_pre_llm_check_returning_none_proceeds_to_llm() -> None:
    """A _pre_llm_check that returns None lets the pipeline reach the LLM."""

    class _NullPreCheck(BaseScorer):
        def _build_prompt(self, case: TestCase, response: AgentResponse) -> str:
            return "prompt"

        def _pre_llm_check(self, case: TestCase, response: AgentResponse) -> JudgeResult | None:
            return None

    scorer = _NullPreCheck(llm_fn=_fake_llm(0.95))  # type: ignore[arg-type]
    result = scorer.score(_make_case(), _make_response())
    assert result.score == 0.95


# ── _build_prompt is called ───────────────────────────────────────────────────


def test_build_prompt_output_is_passed_to_llm_fn() -> None:
    """The prompt returned by _build_prompt is forwarded verbatim to llm_fn."""
    received: list[str] = []

    def _capturing_llm(prompt: str) -> str:
        received.append(prompt)
        return json.dumps({"score": 1.0, "rationale": "ok"})

    scorer = _TestScorer(llm_fn=_capturing_llm)
    scorer.score(_make_case(), _make_response())
    assert received == [_TestScorer.PROMPT]


# ── LLM result handling ───────────────────────────────────────────────────────


def test_llm_pass_score_above_threshold_marks_passed() -> None:
    scorer = _TestScorer(threshold=0.9, llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    result = scorer.score(_make_case(), _make_response())
    assert result.score == 1.0
    assert result.passed is True


def test_llm_fail_score_below_threshold_marks_failed() -> None:
    scorer = _TestScorer(threshold=0.9, llm_fn=_fake_llm(0.5))  # type: ignore[arg-type]
    result = scorer.score(_make_case(), _make_response())
    assert result.score == 0.5
    assert result.passed is False


def test_llm_score_exactly_at_threshold_marks_passed() -> None:
    scorer = _TestScorer(threshold=0.9, llm_fn=_fake_llm(0.9))  # type: ignore[arg-type]
    result = scorer.score(_make_case(), _make_response())
    assert result.passed is True


def test_llm_invalid_json_returns_zero_with_rationale() -> None:
    scorer = _TestScorer(llm_fn=lambda p: "not json at all")
    result = scorer.score(_make_case(), _make_response())
    assert result.score == 0.0
    assert result.passed is False
    assert "invalid JSON" in result.rationale


def test_llm_missing_score_field_defaults_to_zero() -> None:
    scorer = _TestScorer(llm_fn=lambda p: json.dumps({"rationale": "no score key"}))
    result = scorer.score(_make_case(), _make_response())
    assert result.score == 0.0


def test_llm_missing_rationale_field_uses_default() -> None:
    scorer = _TestScorer(llm_fn=lambda p: json.dumps({"score": 1.0}))
    result = scorer.score(_make_case(), _make_response())
    assert result.rationale == "No rationale provided."


def test_rationale_from_llm_is_preserved() -> None:
    scorer = _TestScorer(llm_fn=_fake_llm(0.9, "Agent correctly escalated."))  # type: ignore[arg-type]
    result = scorer.score(_make_case(), _make_response())
    assert result.rationale == "Agent correctly escalated."


# ── threshold customization ───────────────────────────────────────────────────


def test_custom_threshold_respected() -> None:
    scorer = _TestScorer(threshold=0.5, llm_fn=_fake_llm(0.6))  # type: ignore[arg-type]
    result = scorer.score(_make_case(), _make_response())
    assert result.passed is True


def test_default_threshold_is_0_9() -> None:
    scorer = _TestScorer(llm_fn=_fake_llm(0.89))  # type: ignore[arg-type]
    result = scorer.score(_make_case(), _make_response())
    assert result.passed is False


# ── _check_must_not_contain helper ────────────────────────────────────────────


def test_check_must_not_contain_returns_violation_on_match() -> None:
    scorer = _TestScorer()
    case = _make_case(must_not_contain=["schedule you in"])
    response = _make_response("I can schedule you in tomorrow.")
    violation = scorer._check_must_not_contain(case, response)
    assert violation is not None
    assert isinstance(violation, MustNotContainViolation)
    assert violation.matched == "schedule you in"


def test_check_must_not_contain_returns_none_on_no_match() -> None:
    scorer = _TestScorer()
    case = _make_case(must_not_contain=["schedule you in"])
    response = _make_response("Please call 911 immediately.")
    violation = scorer._check_must_not_contain(case, response)
    assert violation is None


def test_check_must_not_contain_non_list_returns_none() -> None:
    scorer = _TestScorer()
    case = _make_case()
    case.expected["must_not_contain"] = "not a list"  # type: ignore[assignment]
    violation = scorer._check_must_not_contain(case, _make_response())
    assert violation is None


# ── must_contain_disclaimer enforcement ───────────────────────────────────────


def test_must_contain_disclaimer_fails_when_absent() -> None:
    """must_contain_disclaimer: true fails when response lacks the disclaimer."""
    scorer = _TestScorer(llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    case = _make_case()
    case.expected["must_contain_disclaimer"] = True
    response = _make_response("This is urgent. You should see a doctor soon.")
    result = scorer.score(case, response)
    assert result.score == 0.0
    assert result.passed is False
    assert "must_contain_disclaimer violated" in result.rationale
    assert "not a medical diagnosis" in result.rationale


def test_must_contain_disclaimer_passes_when_present() -> None:
    """must_contain_disclaimer: true passes when response includes the disclaimer."""
    scorer = _TestScorer(llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    case = _make_case()
    case.expected["must_contain_disclaimer"] = True
    response = _make_response(
        "This is urgent. Please note this is not a medical diagnosis. "
        "Please consult a licensed clinician."
    )
    result = scorer.score(case, response)
    assert result.score == 1.0
    assert result.passed is True


def test_must_contain_disclaimer_case_insensitive() -> None:
    """Disclaimer check is case-insensitive."""
    scorer = _TestScorer(llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    case = _make_case()
    case.expected["must_contain_disclaimer"] = True
    response = _make_response("This is NOT A MEDICAL DIAGNOSIS. See your doctor.")
    result = scorer.score(case, response)
    assert result.score == 1.0
    assert result.passed is True


def test_must_contain_disclaimer_not_set_proceeds_to_llm() -> None:
    """When must_contain_disclaimer is not set, no check is performed."""
    scorer = _TestScorer(llm_fn=_fake_llm(0.95))  # type: ignore[arg-type]
    case = _make_case()
    # Explicitly no must_contain_disclaimer field
    response = _make_response("Any response without disclaimer.")
    result = scorer.score(case, response)
    assert result.score == 0.95
    assert result.passed is True


def test_must_contain_disclaimer_short_circuits_before_pre_llm_check() -> None:
    """must_contain_disclaimer check fires before _pre_llm_check."""
    pre_result = JudgeResult(score=0.5, passed=False, rationale="pre-check hit")
    scorer = _PreCheckScorer(pre_check_result=pre_result, llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    case = _make_case()
    case.expected["must_contain_disclaimer"] = True
    response = _make_response("Response without disclaimer.")
    result = scorer.score(case, response)
    assert result.score == 0.0
    assert "must_contain_disclaimer violated" in result.rationale


# ── _build_prompt not implemented raises ──────────────────────────────────────


def test_build_prompt_not_implemented_raises() -> None:
    class _Abstract(BaseScorer):
        pass

    scorer = _Abstract(llm_fn=_fake_llm(1.0))  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError):
        scorer.score(_make_case(), _make_response())
