"""Structural tests for demo/orchestrator-v1.yaml.

Validates that:
- orchestrator-v1.yaml parses as valid YAML
- Required top-level fields are present (name, description, system_prompt, tools)
- Exactly 3 routing tools are defined: route_to_triage, route_to_eligibility,
  route_to_scheduling
- Each tool has a description and parameters block with required properties
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_DEMO_YAML = Path(__file__).parent.parent / "demo" / "orchestrator-v1.yaml"

EXPECTED_TOOL_NAMES = {"record_consent", "route_to_triage", "route_to_eligibility", "route_to_scheduling"}

EXPECTED_TOOL_REQUIRED_PARAMS: dict[str, set[str]] = {
    "record_consent": {"patient_acknowledged"},
    "route_to_triage": {"patient_id", "symptoms"},
    "route_to_eligibility": {"patient_id", "procedure_code", "payer_id"},
    "route_to_scheduling": {"patient_id", "intent", "message"},
}


@pytest.fixture(scope="module")
def demo_yaml() -> dict:
    with _DEMO_YAML.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@pytest.fixture(scope="module")
def tools(demo_yaml) -> list[dict]:
    return demo_yaml["tools"]


@pytest.fixture(scope="module")
def tools_by_name(tools) -> dict[str, dict]:
    return {t["name"]: t for t in tools}


def test_demo_orchestrator_yaml_is_valid_yaml():
    with _DEMO_YAML.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    assert isinstance(data, dict)


@pytest.mark.parametrize("field", ["name", "description", "system_prompt", "tools"])
def test_required_top_level_fields_present(demo_yaml, field):
    assert field in demo_yaml, f"Missing required field: {field}"


def test_name_is_string(demo_yaml):
    assert isinstance(demo_yaml["name"], str)
    assert demo_yaml["name"]


def test_system_prompt_is_non_empty_string(demo_yaml):
    assert isinstance(demo_yaml["system_prompt"], str)
    assert len(demo_yaml["system_prompt"]) > 50


def test_tools_is_list(demo_yaml):
    assert isinstance(demo_yaml["tools"], list)


def test_exactly_four_tools(tools):
    assert len(tools) == 4


def test_all_expected_tools_present(tools_by_name):
    assert set(tools_by_name.keys()) == EXPECTED_TOOL_NAMES


@pytest.mark.parametrize("tool_name", sorted(EXPECTED_TOOL_NAMES))
def test_tool_has_description(tools_by_name, tool_name):
    tool = tools_by_name[tool_name]
    assert "description" in tool
    assert isinstance(tool["description"], str)
    assert tool["description"].strip()


@pytest.mark.parametrize("tool_name", sorted(EXPECTED_TOOL_NAMES))
def test_tool_has_parameters_block(tools_by_name, tool_name):
    tool = tools_by_name[tool_name]
    assert "parameters" in tool
    params = tool["parameters"]
    assert isinstance(params, dict)
    assert params.get("type") == "object"
    assert "properties" in params


@pytest.mark.parametrize("tool_name", sorted(EXPECTED_TOOL_NAMES))
def test_tool_required_params_declared(tools_by_name, tool_name):
    params = tools_by_name[tool_name]["parameters"]
    required = set(params.get("required", []))
    expected = EXPECTED_TOOL_REQUIRED_PARAMS[tool_name]
    assert expected <= required, (
        f"Tool '{tool_name}' missing required params: {expected - required}"
    )


@pytest.mark.parametrize("tool_name", sorted(EXPECTED_TOOL_NAMES))
def test_tool_properties_match_required(tools_by_name, tool_name):
    params = tools_by_name[tool_name]["parameters"]
    properties = set(params.get("properties", {}).keys())
    required = EXPECTED_TOOL_REQUIRED_PARAMS[tool_name]
    assert required <= properties, (
        f"Tool '{tool_name}' required params not in properties: {required - properties}"
    )


def test_no_x_harness_block_in_demo_yaml(demo_yaml):
    """Demo YAML is not an eval config — it must not have an x-harness block."""
    assert "x-harness" not in demo_yaml


def test_demo_orchestrator_prompt_contains_hipaa_consent_step(demo_yaml):
    prompt = demo_yaml["system_prompt"].lower()
    assert "hipaa" in prompt
    assert "consent" in prompt or "acknowledg" in prompt
