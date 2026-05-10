"""Tests for the advance_turn() contract.

Covers three scenarios for EvalController._run_case():
- Adapter.run() returning None must raise AssertionError.
- Adapter returning AgentResponse with empty trajectory must NOT raise (valid zero-tool case).
- Adapter returning AgentResponse with non-empty trajectory must work correctly.
"""

from __future__ import annotations

import pytest

from hlsharness.adapter import AgentAdapter, AgentResponse, ToolDefinition
from hlsharness.controller import EvalController
from hlsharness.judge import JudgeResult
from hlsharness.loader import TestCase
from hlsharness.simulator import ToolSimulator

# ── Minimal fake judge ──────────────────────────────────────────────────────


class _FakeJudge:
    def score(self, category: str, case: TestCase, response: AgentResponse) -> JudgeResult:
        return JudgeResult(score=1.0, passed=True, rationale="OK")


# ── Fake adapters ───────────────────────────────────────────────────────────


class _NoneAdapter(AgentAdapter):
    """Intentionally broken adapter that returns None instead of an AgentResponse."""

    @property
    def name(self) -> str:
        return "scheduling-v1"

    @property
    def system_prompt(self) -> str:
        return "Fake"

    @property
    def tools(self) -> list[ToolDefinition]:
        return []

    def run(  # type: ignore[return-value]
        self,
        messages: list[dict[str, object]],
        tool_simulator: ToolSimulator,
    ) -> AgentResponse:
        return None  # type: ignore[return-value]


class _EmptyTrajectoryAdapter(AgentAdapter):
    """Valid adapter that responds directly without calling any tools."""

    @property
    def name(self) -> str:
        return "scheduling-v1"

    @property
    def system_prompt(self) -> str:
        return "Fake"

    @property
    def tools(self) -> list[ToolDefinition]:
        return []

    def run(
        self,
        messages: list[dict[str, object]],
        tool_simulator: ToolSimulator,
    ) -> AgentResponse:
        return AgentResponse(content="Direct response without tools.")


class _NonEmptyTrajectoryAdapter(AgentAdapter):
    """Valid adapter that calls one tool and advances the turn counter."""

    @property
    def name(self) -> str:
        return "scheduling-v1"

    @property
    def system_prompt(self) -> str:
        return "Fake"

    @property
    def tools(self) -> list[ToolDefinition]:
        return []

    def run(
        self,
        messages: list[dict[str, object]],
        tool_simulator: ToolSimulator,
    ) -> AgentResponse:
        tool_simulator.call("check_availability", {"date": "2025-01-01"})
        tool_simulator.advance_turn()
        return AgentResponse(content="Appointment booked.")


# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_controller(adapter: AgentAdapter) -> EvalController:
    from pathlib import Path

    return EvalController(
        adapter=adapter,
        judge=_FakeJudge(),
        cases_path=Path("cases"),
    )


def _make_case(
    tool_responses: dict[str, dict[str, object]] | None = None,
) -> TestCase:
    return TestCase(
        id="TC-ADV-001",
        agent="scheduling-v1",
        category="functional",
        input={"messages": [{"role": "user", "content": "Book me an appointment."}]},
        tool_responses=tool_responses or {},
        expected={"outcome": "booked"},
    )


# ── Tests ───────────────────────────────────────────────────────────────────


def test_none_response_raises_assertion_error() -> None:
    """Adapter.run() returning None must cause AssertionError in _run_case()."""
    controller = _make_controller(_NoneAdapter())
    case = _make_case()

    with pytest.raises(AssertionError, match=r"_NoneAdapter\.run\(\) returned None"):
        controller._run_case(case)


def test_empty_trajectory_does_not_raise() -> None:
    """Zero-tool-call case: empty trajectory is valid and must not raise."""
    controller = _make_controller(_EmptyTrajectoryAdapter())
    case = _make_case()

    result = controller._run_case(case)

    assert result.trajectory == []


def test_non_empty_trajectory_works_correctly() -> None:
    """Adapter that calls advance_turn() records tool calls in the trajectory."""
    tool_responses: dict[str, dict[str, object]] = {
        "check_availability": {"slots": ["2025-01-01T10:00"]}
    }
    controller = _make_controller(_NonEmptyTrajectoryAdapter())
    case = _make_case(tool_responses=tool_responses)

    result = controller._run_case(case)

    assert len(result.trajectory) == 1
    assert result.trajectory[0]["tool_name"] == "check_availability"
    assert result.trajectory[0]["turn"] == 0
