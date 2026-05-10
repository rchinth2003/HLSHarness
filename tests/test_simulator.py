"""Unit tests for ToolSimulator — no Azure credentials required."""

import pytest

from hlsharness.simulator import ToolSimulator, UnknownToolError


def test_call_returns_scripted_response():
    sim = ToolSimulator({"search_available_slots": {"slots": [{"id": "s1"}]}})
    result = sim.call(
        "search_available_slots",
        {"provider_id": "P1", "date_range_start": "2026-05-18", "date_range_end": "2026-05-25"},
    )
    assert result == {"slots": [{"id": "s1"}]}


def test_call_records_trajectory():
    sim = ToolSimulator({"book_appointment": {"status": "confirmed"}})
    sim.call("book_appointment", {"patient_id": "PAT-1", "slot_id": "slot-001"})
    assert len(sim.trajectory) == 1
    entry = sim.trajectory[0]
    assert entry.tool_name == "book_appointment"
    assert entry.arguments == {"patient_id": "PAT-1", "slot_id": "slot-001"}
    assert entry.response == {"status": "confirmed"}
    assert entry.turn == 0


def test_advance_turn_increments_turn_counter():
    sim = ToolSimulator({"tool_a": {"ok": True}, "tool_b": {"ok": True}})
    sim.call("tool_a", {})
    sim.advance_turn()
    sim.call("tool_b", {})
    assert sim.trajectory[0].turn == 0
    assert sim.trajectory[1].turn == 1


def test_multiple_calls_same_tool_all_recorded():
    sim = ToolSimulator({"search_available_slots": {"slots": []}})
    sim.call(
        "search_available_slots",
        {"provider_id": "P1", "date_range_start": "2026-05-18", "date_range_end": "2026-05-19"},
    )
    sim.call(
        "search_available_slots",
        {"provider_id": "P2", "date_range_start": "2026-05-18", "date_range_end": "2026-05-19"},
    )
    assert len(sim.trajectory) == 2


def test_unknown_tool_raises():
    sim = ToolSimulator({"book_appointment": {"status": "confirmed"}})
    with pytest.raises(UnknownToolError, match="search_available_slots"):
        sim.call("search_available_slots", {})


def test_trajectory_is_copy():
    """Mutating the returned trajectory must not affect the simulator's internal state."""
    sim = ToolSimulator({"tool_a": {}})
    sim.call("tool_a", {})
    traj = sim.trajectory
    traj.clear()
    assert len(sim.trajectory) == 1
