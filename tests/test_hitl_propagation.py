"""HITL signal propagation tests — validates escalation signals from real case YAMLs.

Loads TC-O-002/003/004 (ambiguous_intent, eligibility_failure) from disk and feeds
their expected signals to HITLRoutingScorer._pre_llm_check(). No LLM calls made.

Covers: reason codes in VALID_REASON_CODES catalog, valid signals pass through to LLM,
malformed signals return correct JudgeResult, partial credit on wrong-but-valid reason.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from hlsharness.hitl_routing import VALID_REASON_CODES, HITLRoutingScorer
from hlsharness.loader import TestCase
from hlsharness.results import AgentResponse

_HITL_DIR = Path(__file__).parent.parent / "cases" / "orchestrator-v1" / "hitl_routing"

_SCORER = HITLRoutingScorer(
    threshold=0.9,
    llm_fn=lambda _: '{"score": 0.9, "rationale": "test stub"}',
)


# ── helpers ───────────────────────────────────────────────────────────────────


def _load_case(filename: str) -> TestCase:
    data = yaml.safe_load((_HITL_DIR / filename).read_text(encoding="utf-8"))
    return TestCase(
        id=data["id"],
        agent=data["agent"],
        category=data["category"],
        input=data["input"],
        tool_responses={},
        expected=data["expected"],
        metadata=data.get("metadata", {}),
    )


def _signal_response(signal: dict) -> AgentResponse:
    return AgentResponse(content=json.dumps(signal))


# ── reason code catalog ───────────────────────────────────────────────────────


def test_tc_o_002_reason_code_in_valid_catalog() -> None:
    case = _load_case("TC-O-002.yaml")
    assert case.expected["reason_code"] in VALID_REASON_CODES


def test_tc_o_003_reason_code_in_valid_catalog() -> None:
    case = _load_case("TC-O-003.yaml")
    assert case.expected["reason_code"] in VALID_REASON_CODES


def test_tc_o_004_reason_code_in_valid_catalog() -> None:
    case = _load_case("TC-O-004.yaml")
    assert case.expected["reason_code"] in VALID_REASON_CODES


def test_tc_o_002_reason_code_is_ambiguous_intent() -> None:
    case = _load_case("TC-O-002.yaml")
    assert case.expected["reason_code"] == "ambiguous_intent"


def test_tc_o_003_reason_code_is_ambiguous_intent() -> None:
    case = _load_case("TC-O-003.yaml")
    assert case.expected["reason_code"] == "ambiguous_intent"


def test_tc_o_004_reason_code_is_eligibility_failure() -> None:
    case = _load_case("TC-O-004.yaml")
    assert case.expected["reason_code"] == "eligibility_failure"


# ── pre-LLM check: valid signals pass through to LLM ─────────────────────────


def test_tc_o_002_valid_ambiguous_intent_signal_passes_pre_llm_check() -> None:
    case = _load_case("TC-O-002.yaml")
    response = _signal_response(
        {"escalate": True, "reason": "ambiguous_intent", "confidence": 0.85}
    )
    result = _SCORER._pre_llm_check(case, response)
    assert result is None  # None → proceeds to LLM rubric


def test_tc_o_003_valid_ambiguous_intent_signal_passes_pre_llm_check() -> None:
    case = _load_case("TC-O-003.yaml")
    response = _signal_response(
        {"escalate": True, "reason": "ambiguous_intent", "confidence": 0.90}
    )
    result = _SCORER._pre_llm_check(case, response)
    assert result is None


def test_tc_o_004_valid_eligibility_failure_signal_passes_pre_llm_check() -> None:
    case = _load_case("TC-O-004.yaml")
    response = _signal_response(
        {"escalate": True, "reason": "eligibility_failure", "confidence": 0.95}
    )
    result = _SCORER._pre_llm_check(case, response)
    assert result is None


# ── pre-LLM check: malformed signals return zero ─────────────────────────────


def test_pre_llm_check_missing_signal_returns_zero_when_escalation_expected() -> None:
    case = _load_case("TC-O-002.yaml")  # expects escalate=true
    response = AgentResponse(content="I can help you schedule an appointment.")
    result = _SCORER._pre_llm_check(case, response)
    assert result is not None
    assert result.score == pytest.approx(0.0)
    assert result.passed is False


def test_pre_llm_check_invalid_reason_code_returns_zero() -> None:
    case = _load_case("TC-O-002.yaml")
    response = _signal_response({"escalate": True, "reason": "unknown_reason", "confidence": 0.8})
    result = _SCORER._pre_llm_check(case, response)
    assert result is not None
    assert result.score == pytest.approx(0.0)
    assert result.passed is False


def test_pre_llm_check_wrong_escalate_flag_returns_zero() -> None:
    case = _load_case("TC-O-002.yaml")  # expects escalate=true
    response = _signal_response(
        {"escalate": False, "reason": "ambiguous_intent", "confidence": 0.85}
    )
    result = _SCORER._pre_llm_check(case, response)
    assert result is not None
    assert result.score == pytest.approx(0.0)
    assert result.passed is False


def test_pre_llm_check_confidence_out_of_range_returns_zero() -> None:
    case = _load_case("TC-O-002.yaml")
    response = _signal_response({"escalate": True, "reason": "ambiguous_intent", "confidence": 1.5})
    result = _SCORER._pre_llm_check(case, response)
    assert result is not None
    assert result.score == pytest.approx(0.0)
    assert result.passed is False


# ── pre-LLM check: partial credit for valid-but-wrong reason code ─────────────


def test_pre_llm_check_valid_reason_mismatch_returns_partial_credit() -> None:
    # TC-O-002 expects ambiguous_intent; agent emits eligibility_failure (valid but wrong)
    case = _load_case("TC-O-002.yaml")
    response = _signal_response(
        {"escalate": True, "reason": "eligibility_failure", "confidence": 0.8}
    )
    result = _SCORER._pre_llm_check(case, response)
    assert result is not None
    assert result.score == pytest.approx(0.5)
    assert result.passed is False
