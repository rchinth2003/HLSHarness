"""Import-safety tests for demo/runner.py.

Verifies that DemoRunner, TurnResult, and TraceEvent are importable without
Azure credentials set in the environment and that constructing a DemoRunner
instance does not raise (lazy Azure init).
"""

from __future__ import annotations

from pathlib import Path


def test_demo_runner_module_importable():
    """demo.runner is importable without any Azure environment variables."""
    import demo.runner  # noqa: F401


def test_trace_event_importable():
    from demo.runner import TraceEvent  # noqa: F401

    assert TraceEvent is not None


def test_turn_result_importable():
    from demo.runner import TurnResult  # noqa: F401

    assert TurnResult is not None


def test_demo_runner_importable():
    from demo.runner import DemoRunner  # noqa: F401

    assert DemoRunner is not None


def test_demo_runner_constructor_does_not_raise():
    """Constructing DemoRunner must not touch Azure or load any files."""
    from demo.runner import DemoRunner

    runner = DemoRunner("happy_path_booking")
    assert runner is not None


def test_demo_runner_accepts_repo_root_kwarg():
    from demo.runner import DemoRunner

    runner = DemoRunner("happy_path_booking", repo_root=Path("."))
    assert runner._root == Path(".")


def test_trace_event_fields():
    from demo.runner import TraceEvent

    event = TraceEvent(
        sub_agent="scheduling-v1",
        tool_name="search_available_slots",
        fixture_name="full_slots",
        stub_response={"slots": []},
        hitl_signal=None,
    )
    assert event.sub_agent == "scheduling-v1"
    assert event.tool_name == "search_available_slots"
    assert event.fixture_name == "full_slots"
    assert event.hitl_signal is None


def test_turn_result_fields():
    from demo.runner import TurnResult

    result = TurnResult(
        orchestrator_reply="Your appointment is confirmed.",
        trace_events=[],
        hitl_signal=None,
    )
    assert result.orchestrator_reply == "Your appointment is confirmed."
    assert result.trace_events == []
    assert result.hitl_signal is None


def test_extract_hitl_finds_signal():
    from demo.runner import _extract_hitl

    text = 'The agent says {"escalate": true, "reason": "eligibility_failure", "confidence": 0.95}'
    signal = _extract_hitl(text)
    assert signal is not None
    assert signal["escalate"] is True
    assert signal["reason"] == "eligibility_failure"


def test_extract_hitl_returns_none_when_absent():
    from demo.runner import _extract_hitl

    assert _extract_hitl("Coverage confirmed. Your co-pay is $30.") is None


def test_build_sub_agent_message_triage():
    from demo.runner import _build_sub_agent_message

    msg = _build_sub_agent_message(
        "route_to_triage", {"patient_id": "P-001", "symptoms": "chest pain"}
    )
    assert "chest pain" in msg
    assert "P-001" in msg


def test_build_sub_agent_message_eligibility():
    from demo.runner import _build_sub_agent_message

    msg = _build_sub_agent_message(
        "route_to_eligibility",
        {"patient_id": "P-001", "procedure_code": "99213", "payer_id": "BCBS-001"},
    )
    assert "P-001" in msg
    assert "99213" in msg


def test_build_sub_agent_message_scheduling_uses_message_field():
    from demo.runner import _build_sub_agent_message

    msg = _build_sub_agent_message(
        "route_to_scheduling",
        {"patient_id": "P-001", "intent": "book", "message": "Book me a slot on Friday"},
    )
    assert msg == "Book me a slot on Friday"
