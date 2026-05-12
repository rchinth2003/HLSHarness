"""Structural tests for cases/triage-v1 — no agent execution, no LLM calls.

Validates that agent.yaml and all case YAMLs are well-formed. All assertions
are against static file content.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_CASES_ROOT = Path(__file__).parent.parent / "cases" / "triage-v1"
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
    assert data["name"] == "triage-v1"


def test_agent_yaml_no_tools() -> None:
    data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    assert data.get("tools") == [] or data.get("tools") is None


def test_agent_yaml_categories() -> None:
    data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    categories = data["x-harness"]["categories"]
    assert "urgency_triage" in categories
    assert "safety" in categories
    assert "hitl_routing" in categories


def test_agent_yaml_thresholds() -> None:
    data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    thresholds = data["x-harness"]["thresholds"]
    assert thresholds["urgency_triage"] == pytest.approx(0.90)
    assert thresholds["safety"] == pytest.approx(0.90)
    assert thresholds["hitl_routing"] == pytest.approx(0.90)


# ── case file discovery ───────────────────────────────────────────────────────


def _all_case_files() -> list[Path]:
    return sorted(_CASES_ROOT.rglob("TC-*.yaml"))


def test_exactly_thirty_case_files() -> None:
    assert len(_all_case_files()) == 30


def test_fourteen_urgency_triage_cases() -> None:
    urgency = sorted((_CASES_ROOT / "urgency_triage").glob("TC-*.yaml"))
    assert len(urgency) == 14


def test_ten_safety_cases() -> None:
    safety = sorted((_CASES_ROOT / "safety").glob("TC-*.yaml"))
    assert len(safety) == 10


def test_six_hitl_routing_cases() -> None:
    hitl = sorted((_CASES_ROOT / "hitl_routing").glob("TC-*.yaml"))
    assert len(hitl) == 6


# ── per-case structural validation ───────────────────────────────────────────

_REQUIRED_FIELDS = {"id", "agent", "category", "input", "tool_responses", "expected"}


@pytest.mark.parametrize("case_file", _all_case_files(), ids=lambda p: p.name)
def test_case_has_required_fields(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    missing = _REQUIRED_FIELDS - set(data)
    assert not missing, f"{case_file.name} missing fields: {missing}"


@pytest.mark.parametrize("case_file", _all_case_files(), ids=lambda p: p.name)
def test_case_agent_matches_triage(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    assert data["agent"] == "triage-v1"


@pytest.mark.parametrize("case_file", _all_case_files(), ids=lambda p: p.name)
def test_case_category_matches_directory(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    expected_category = case_file.parent.name
    assert data["category"] == expected_category


@pytest.mark.parametrize("case_file", _all_case_files(), ids=lambda p: p.name)
def test_case_tool_responses_is_empty(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    assert data["tool_responses"] == {} or data["tool_responses"] is None


@pytest.mark.parametrize("case_file", _all_case_files(), ids=lambda p: p.name)
def test_case_has_user_message(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    messages = data["input"]["messages"]
    assert any(m["role"] == "user" for m in messages)


# ── urgency_triage case-specific validation ───────────────────────────────────

_VALID_TRIAGE_LEVELS = {"emergent", "urgent", "routine"}


@pytest.mark.parametrize(
    "case_file",
    sorted((_CASES_ROOT / "urgency_triage").glob("TC-*.yaml")),
    ids=lambda p: p.name,
)
def test_urgency_triage_case_has_triage_level(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    level = data["expected"].get("triage_level")
    assert level in _VALID_TRIAGE_LEVELS, f"{case_file.name}: invalid triage_level '{level}'"


@pytest.mark.parametrize(
    "case_file",
    sorted((_CASES_ROOT / "urgency_triage").glob("TC-*.yaml")),
    ids=lambda p: p.name,
)
def test_urgency_triage_case_has_outcome(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    assert data["expected"].get("outcome"), f"{case_file.name}: missing 'outcome'"


# ── safety case-specific validation ──────────────────────────────────────────

_VALID_SEVERITY_LEVELS = {"HIGH", "MEDIUM"}


@pytest.mark.parametrize(
    "case_file",
    sorted((_CASES_ROOT / "safety").glob("TC-*.yaml")),
    ids=lambda p: p.name,
)
def test_safety_case_has_severity(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    severity = data["expected"].get("severity")
    assert severity in _VALID_SEVERITY_LEVELS, f"{case_file.name}: invalid severity '{severity}'"


@pytest.mark.parametrize(
    "case_file",
    sorted((_CASES_ROOT / "safety").glob("TC-*.yaml")),
    ids=lambda p: p.name,
)
def test_safety_case_has_outcome(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    assert data["expected"].get("outcome"), f"{case_file.name}: missing 'outcome'"


# ── hitl_routing case-specific validation ────────────────────────────────────


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
def test_hitl_case_reason_code_is_red_flag_symptom(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    reason = data["expected"].get("reason_code")
    assert reason == "red_flag_symptom", (
        f"{case_file.name}: expected reason_code 'red_flag_symptom', got '{reason}'"
    )
