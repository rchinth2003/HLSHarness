"""Structural tests for demo/scenarios.yaml.

Validates that:
- scenarios.yaml parses as valid YAML
- Exactly 6 scenarios are defined
- Each scenario has required fields (name, persona_id, stub_map)
- All persona_id values reference files that exist in personas/
- All stub_map fixture names reference files that exist in stubs/
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_DEMO_DIR = Path(__file__).parent.parent / "demo"
_PERSONAS_DIR = Path(__file__).parent.parent / "personas"
_STUBS_DIR = Path(__file__).parent.parent / "stubs"
_SCENARIOS_PATH = _DEMO_DIR / "scenarios.yaml"

EXPECTED_SCENARIO_COUNT = 6
EXPECTED_SCENARIO_NAMES = {
    "happy_path_booking",
    "prior_auth_approved",
    "prior_auth_denied_hitl",
    "no_slots_hitl",
    "red_flag_triage_hitl",
    "out_of_network_hitl",
}


@pytest.fixture(scope="module")
def scenarios_data() -> dict:
    with _SCENARIOS_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@pytest.fixture(scope="module")
def scenarios(scenarios_data) -> list[dict]:
    return scenarios_data["scenarios"]


def test_scenarios_yaml_is_valid_yaml():
    """scenarios.yaml parses without error."""
    with _SCENARIOS_PATH.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    assert isinstance(data, dict)


def test_scenarios_yaml_has_scenarios_key(scenarios_data):
    assert "scenarios" in scenarios_data


def test_exactly_six_scenarios(scenarios):
    assert len(scenarios) == EXPECTED_SCENARIO_COUNT


def test_all_expected_scenario_names_present(scenarios):
    names = {sc["name"] for sc in scenarios}
    assert names == EXPECTED_SCENARIO_NAMES


@pytest.mark.parametrize("field", ["name", "persona_id", "stub_map"])
def test_each_scenario_has_required_field(scenarios, field):
    for sc in scenarios:
        assert field in sc, f"Scenario '{sc.get('name', '?')}' missing field '{field}'"


def test_all_persona_ids_exist_on_disk(scenarios):
    for sc in scenarios:
        persona_id = sc["persona_id"]
        persona_file = _PERSONAS_DIR / f"{persona_id}.yaml"
        assert persona_file.exists(), (
            f"Scenario '{sc['name']}': persona '{persona_id}' not found at {persona_file}"
        )


def test_all_stub_fixtures_exist_on_disk(scenarios):
    for sc in scenarios:
        stub_map = sc.get("stub_map") or {}
        for agent_name, tool_map in stub_map.items():
            if not isinstance(tool_map, dict):
                continue
            for tool_name, fixture_name in tool_map.items():
                fixture_path = _STUBS_DIR / agent_name / tool_name / f"{fixture_name}.yaml"
                assert fixture_path.exists(), (
                    f"Scenario '{sc['name']}': stub '{agent_name}/{tool_name}/{fixture_name}' "
                    f"not found at {fixture_path}"
                )


def test_each_stub_fixture_is_valid_yaml(scenarios):
    for sc in scenarios:
        stub_map = sc.get("stub_map") or {}
        for agent_name, tool_map in stub_map.items():
            if not isinstance(tool_map, dict):
                continue
            for tool_name, fixture_name in tool_map.items():
                fixture_path = _STUBS_DIR / agent_name / tool_name / f"{fixture_name}.yaml"
                if fixture_path.exists():
                    with fixture_path.open(encoding="utf-8") as fh:
                        data = yaml.safe_load(fh)
                    assert isinstance(data, dict), f"Fixture {fixture_path} is not a YAML mapping"


def test_red_flag_triage_hitl_has_empty_stub_map(scenarios):
    sc = next(s for s in scenarios if s["name"] == "red_flag_triage_hitl")
    assert not sc.get("stub_map")


def test_happy_path_has_eligibility_and_scheduling_stubs(scenarios):
    sc = next(s for s in scenarios if s["name"] == "happy_path_booking")
    stub_map = sc["stub_map"]
    assert "eligibility-v1" in stub_map
    assert "scheduling-v1" in stub_map
