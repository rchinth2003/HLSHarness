"""Unit tests for EvalController upfront validation — no Azure credentials required."""

from __future__ import annotations

from pathlib import Path

import pytest

from hlsharness.adapter import AgentAdapter, AgentResponse, ToolDefinition
from hlsharness.controller import CaseValidationError, EvalController
from hlsharness.judge import JudgeResult
from hlsharness.loader import TestCase
from hlsharness.simulator import ToolSimulator


class _FakeJudge:
    def score(self, category: str, case: TestCase, response: AgentResponse) -> JudgeResult:
        return JudgeResult(score=1.0, passed=True, rationale="ok")


class _AdapterWithTools(AgentAdapter):
    def __init__(self, tool_names: list[str]) -> None:
        self._tools = [ToolDefinition(name=n, description="") for n in tool_names]

    @property
    def name(self) -> str:
        return "scheduling-v1"

    @property
    def system_prompt(self) -> str:
        return ""

    @property
    def tools(self) -> list[ToolDefinition]:
        return self._tools

    def run(self, messages: list[dict], tool_simulator: ToolSimulator) -> AgentResponse:  # type: ignore[override]
        return AgentResponse(content="ok", prompt_tokens=0, completion_tokens=0)


def _make_controller(tool_names: list[str]) -> EvalController:
    return EvalController(
        adapter=_AdapterWithTools(tool_names),
        judge=_FakeJudge(),  # type: ignore[arg-type]
        cases_path=Path("cases"),
    )


def _equity_case(
    case_id: str = "TC-V-001",
    tool_responses: dict | None = None,
    metadata: dict | None = None,
) -> TestCase:
    return TestCase(
        id=case_id,
        agent="scheduling-v1",
        category="equity",
        input={"messages": [{"role": "user", "content": "hi"}]},
        tool_responses=tool_responses or {},
        expected={"outcome": "provide_equivalent_service", "severity": "high"},
        metadata=metadata
        if metadata is not None
        else {"patient_age": 45, "language": "english", "insurance": "medicaid"},
    )


def _functional_case(tool_responses: dict | None = None) -> TestCase:
    return TestCase(
        id="TC-V-002",
        agent="scheduling-v1",
        category="functional",
        input={"messages": [{"role": "user", "content": "hi"}]},
        tool_responses=tool_responses or {},
        expected={"outcome": "book_appointment"},
        metadata={},
    )


# ── tool_responses validation ─────────────────────────────────────────────────


def test_unknown_tool_raises_before_any_case_runs(tmp_path: Path) -> None:
    controller = _make_controller(tool_names=["book_appointment"])
    case = _functional_case(tool_responses={"typo_tool": "response"})
    with pytest.raises(CaseValidationError, match="typo_tool"):
        controller._validate_cases([case])


def test_valid_tool_name_does_not_raise() -> None:
    controller = _make_controller(tool_names=["book_appointment"])
    case = _functional_case(tool_responses={"book_appointment": "booked"})
    controller._validate_cases([case])  # no exception


def test_adapter_with_no_tools_and_empty_tool_responses_does_not_raise() -> None:
    controller = _make_controller(tool_names=[])
    case = _functional_case(tool_responses={})
    controller._validate_cases([case])  # no exception


# ── equity metadata validation ────────────────────────────────────────────────


def test_equity_missing_patient_age_raises() -> None:
    controller = _make_controller(tool_names=[])
    case = _equity_case(metadata={"language": "english", "insurance": "medicaid"})
    with pytest.raises(CaseValidationError, match="patient_age"):
        controller._validate_cases([case])


def test_equity_missing_language_raises() -> None:
    controller = _make_controller(tool_names=[])
    case = _equity_case(metadata={"patient_age": 45, "insurance": "medicaid"})
    with pytest.raises(CaseValidationError, match="language"):
        controller._validate_cases([case])


def test_equity_missing_insurance_raises() -> None:
    controller = _make_controller(tool_names=[])
    case = _equity_case(metadata={"patient_age": 45, "language": "english"})
    with pytest.raises(CaseValidationError, match="insurance"):
        controller._validate_cases([case])


def test_equity_with_all_keys_does_not_raise() -> None:
    controller = _make_controller(tool_names=[])
    case = _equity_case(
        metadata={"patient_age": 45, "language": "english", "insurance": "medicaid"}
    )
    controller._validate_cases([case])  # no exception


def test_non_equity_case_not_checked_for_equity_metadata() -> None:
    controller = _make_controller(tool_names=[])
    case = _functional_case()
    case.metadata = {}  # missing equity keys — should not raise for non-equity
    controller._validate_cases([case])  # no exception


# ── multiple errors reported together ─────────────────────────────────────────


def test_multiple_errors_across_cases_reported_in_one_exception() -> None:
    controller = _make_controller(tool_names=["book_appointment"])
    cases = [
        _functional_case(tool_responses={"bad_tool": "x"}),
        _equity_case(
            case_id="TC-V-003",
            metadata={"patient_age": 45},  # missing language + insurance
        ),
    ]
    with pytest.raises(CaseValidationError) as exc_info:
        controller._validate_cases(cases)
    message = str(exc_info.value)
    assert "bad_tool" in message
    assert "language" in message
    assert "insurance" in message
