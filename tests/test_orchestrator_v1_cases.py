"""Structural tests for cases/orchestrator-v1 — no agent execution, no LLM calls.

Validates that all case YAMLs are well-formed and the agent.yaml has the
required harness fields. All assertions are against static file content.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_CASES_ROOT = Path(__file__).parent.parent / "cases" / "orchestrator-v1"
_AGENT_YAML = _CASES_ROOT / "agent.yaml"


# ── agent.yaml structure ──────────────────────────────────────────────────────


def test_agent_yaml_exists() -> None:
    assert _AGENT_YAML.exists(), f"agent.yaml not found at {_AGENT_YAML}"


def test_agent_yaml_has_required_fields() -> None:
    data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    for field in ("name", "description", "system_prompt", "x-harness"):
        assert field in data, f"agent.yaml missing field: {field}"


def test_agent_yaml_name() -> None:
    data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    assert data["name"] == "orchestrator-v1"


def test_agent_yaml_categories() -> None:
    data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    categories = data["x-harness"]["categories"]
    assert "functional" in categories
    assert "hitl_routing" in categories


def test_agent_yaml_thresholds() -> None:
    data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    thresholds = data["x-harness"]["thresholds"]
    assert thresholds["functional"] == pytest.approx(0.80)
    assert thresholds["hitl_routing"] == pytest.approx(0.90)


def test_agent_yaml_no_tools() -> None:
    data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    assert data.get("tools") == [] or data.get("tools") is None


# ── case file discovery ───────────────────────────────────────────────────────


def _all_case_files() -> list[Path]:
    return sorted(_CASES_ROOT.rglob("TC-*.yaml"))


def test_exactly_six_case_files() -> None:
    assert len(_all_case_files()) == 6


def test_two_functional_cases() -> None:
    functional = sorted((_CASES_ROOT / "functional").glob("TC-*.yaml"))
    assert len(functional) == 2


def test_four_hitl_routing_cases() -> None:
    hitl = sorted((_CASES_ROOT / "hitl_routing").glob("TC-*.yaml"))
    assert len(hitl) == 4


# ── per-case structural validation ───────────────────────────────────────────

_REQUIRED_FIELDS = {"id", "agent", "category", "input", "tool_responses", "expected"}


@pytest.mark.parametrize("case_file", _all_case_files(), ids=lambda p: p.name)
def test_case_has_required_fields(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    missing = _REQUIRED_FIELDS - set(data)
    assert not missing, f"{case_file.name} missing fields: {missing}"


@pytest.mark.parametrize("case_file", _all_case_files(), ids=lambda p: p.name)
def test_case_agent_matches_orchestrator(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    assert data["agent"] == "orchestrator-v1"


@pytest.mark.parametrize("case_file", _all_case_files(), ids=lambda p: p.name)
def test_case_category_matches_directory(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    expected_category = case_file.parent.name
    assert data["category"] == expected_category


@pytest.mark.parametrize("case_file", _all_case_files(), ids=lambda p: p.name)
def test_case_has_user_message(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    messages = data["input"]["messages"]
    assert any(m["role"] == "user" for m in messages)


# ── hitl_routing case-specific validation ────────────────────────────────────

_VALID_REASON_CODES = {
    "ambiguous_intent",
    "consent_declined",
    "eligibility_failure",
    "no_available_slots",
    "red_flag_symptom",
    "late_cancellation_policy",
}


@pytest.mark.parametrize(
    "case_file",
    sorted((_CASES_ROOT / "hitl_routing").glob("TC-*.yaml")),
    ids=lambda p: p.name,
)
def test_hitl_case_expects_escalation(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    assert data["expected"].get("escalate") is True


@pytest.mark.parametrize(
    "case_file",
    sorted((_CASES_ROOT / "hitl_routing").glob("TC-*.yaml")),
    ids=lambda p: p.name,
)
def test_hitl_case_reason_code_valid(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    reason = data["expected"].get("reason_code")
    assert reason in _VALID_REASON_CODES, f"{case_file.name}: invalid reason_code '{reason}'"


# ── functional case-specific validation ──────────────────────────────────────


@pytest.mark.parametrize(
    "case_file",
    sorted((_CASES_ROOT / "functional").glob("TC-*.yaml")),
    ids=lambda p: p.name,
)
def test_functional_case_no_escalation_expected(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    assert data["expected"].get("escalate") is False
