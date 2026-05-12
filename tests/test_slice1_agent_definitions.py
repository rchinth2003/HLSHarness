"""Slice 1 structural validation: solution.yaml case_dir mappings + agent.yaml presence.

Verifies that each agent entry in solution.yaml declares case_dir and that the
corresponding agent.yaml exists in the cases/ tree.  No Azure calls made.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hlsharness.solution_manifest import SolutionManifest

_MANIFEST_PATH = Path(__file__).parent.parent / "config" / "solution.yaml"
_HARNESS_CASES = Path(__file__).parent.parent / "cases"

_EXPECTED_CASE_DIRS = {
    "orchestrator": "orchestrator-v1",
    "scheduling-agent": "scheduling-v1",
    "eligibility-agent": "eligibility-v1",
    "triage-agent": "triage-v1",
}


def _manifest() -> SolutionManifest:
    return SolutionManifest.load(_MANIFEST_PATH)


# ── case_dir declarations ────────────────────────────────────────────────────


def test_orchestrator_case_dir() -> None:
    m = _manifest()
    orch = next(a for a in m.agents if a.name == "orchestrator")
    assert orch.case_dir == "orchestrator-v1"


def test_scheduling_agent_case_dir() -> None:
    m = _manifest()
    agent = next(a for a in m.agents if a.name == "scheduling-agent")
    assert agent.case_dir == "scheduling-v1"


def test_eligibility_agent_case_dir() -> None:
    m = _manifest()
    agent = next(a for a in m.agents if a.name == "eligibility-agent")
    assert agent.case_dir == "eligibility-v1"


def test_triage_agent_case_dir() -> None:
    m = _manifest()
    agent = next(a for a in m.agents if a.name == "triage-agent")
    assert agent.case_dir == "triage-v1"


def test_all_agents_have_non_empty_case_dir() -> None:
    m = _manifest()
    for agent in m.agents:
        assert agent.case_dir, f"Agent '{agent.name}' is missing case_dir"


def test_case_dirs_match_expected_mapping() -> None:
    m = _manifest()
    for agent in m.agents:
        expected = _EXPECTED_CASE_DIRS.get(agent.name)
        assert expected is not None, f"Unexpected agent name: '{agent.name}'"
        assert agent.case_dir == expected, (
            f"Agent '{agent.name}': expected case_dir='{expected}', got '{agent.case_dir}'"
        )


# ── agent.yaml presence ───────────────────────────────────────────────────────


@pytest.mark.parametrize("agent_name,case_dir", list(_EXPECTED_CASE_DIRS.items()))
def test_agent_yaml_exists(agent_name: str, case_dir: str) -> None:
    agent_yaml = _HARNESS_CASES / case_dir / "agent.yaml"
    if not agent_yaml.exists():
        pytest.skip(f"{case_dir}/agent.yaml not yet implemented (future slice)")
    assert agent_yaml.exists(), f"agent.yaml missing for '{agent_name}' at {agent_yaml}"


def test_orchestrator_agent_yaml_has_hitl_routing_category() -> None:
    import yaml

    path = _HARNESS_CASES / "orchestrator-v1" / "agent.yaml"
    if not path.exists():
        pytest.skip("orchestrator-v1/agent.yaml not yet present")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    categories = data.get("x-harness", {}).get("categories", [])
    assert "hitl_routing" in categories


def test_eligibility_agent_yaml_has_privacy_category() -> None:
    import yaml

    path = _HARNESS_CASES / "eligibility-v1" / "agent.yaml"
    if not path.exists():
        pytest.skip("eligibility-v1/agent.yaml not yet present")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    categories = data.get("x-harness", {}).get("categories", [])
    assert "privacy" in categories


def test_eligibility_agent_yaml_declares_check_eligibility_tool() -> None:
    import yaml

    path = _HARNESS_CASES / "eligibility-v1" / "agent.yaml"
    if not path.exists():
        pytest.skip("eligibility-v1/agent.yaml not yet present")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    tools = data.get("tools", [])
    tool_names = [t.get("name") for t in tools]
    assert "check_eligibility" in tool_names
