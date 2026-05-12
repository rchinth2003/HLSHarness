"""Structural tests for cases/eligibility-v1 — no agent execution, no LLM calls.

Validates that all case YAMLs are well-formed, agent.yaml has required harness
fields, and all three stub fixtures are present and valid YAML.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_CASES_ROOT = Path(__file__).parent.parent / "cases" / "eligibility-v1"
_STUBS_ROOT = Path(__file__).parent.parent / "stubs" / "eligibility-v1" / "check_eligibility"
_AGENT_YAML = _CASES_ROOT / "agent.yaml"


# ── agent.yaml structure ──────────────────────────────────────────────────────


def test_agent_yaml_exists() -> None:
    assert _AGENT_YAML.exists(), f"agent.yaml not found at {_AGENT_YAML}"


def test_agent_yaml_has_required_fields() -> None:
    data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    for field in ("name", "description", "system_prompt", "tools", "x-harness"):
        assert field in data, f"agent.yaml missing field: {field}"


def test_agent_yaml_name() -> None:
    data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    assert data["name"] == "eligibility-v1"


def test_agent_yaml_categories() -> None:
    data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    categories = data["x-harness"]["categories"]
    assert "functional" in categories
    assert "privacy" in categories


def test_agent_yaml_thresholds() -> None:
    data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    thresholds = data["x-harness"]["thresholds"]
    assert thresholds["functional"] == pytest.approx(0.80)
    assert thresholds["privacy"] == pytest.approx(1.00)


def test_agent_yaml_has_check_eligibility_tool() -> None:
    data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    tool_names = [t["name"] for t in data.get("tools", [])]
    assert "check_eligibility" in tool_names


def test_check_eligibility_tool_required_params() -> None:
    data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    tool = next(t for t in data["tools"] if t["name"] == "check_eligibility")
    required = tool["parameters"]["required"]
    assert "patient_id" in required
    assert "procedure_code" in required
    assert "payer_id" in required


# ── stub fixtures ─────────────────────────────────────────────────────────────


def test_three_stub_fixtures_exist() -> None:
    fixtures = sorted(_STUBS_ROOT.glob("*.yaml"))
    names = {f.stem for f in fixtures}
    assert names == {"covered", "not_covered", "prior_auth_required"}


@pytest.mark.parametrize("fixture_name", ["covered", "not_covered", "prior_auth_required"])
def test_stub_fixture_is_valid_yaml(fixture_name: str) -> None:
    fixture_path = _STUBS_ROOT / f"{fixture_name}.yaml"
    data = yaml.safe_load(fixture_path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{fixture_name}.yaml must be a YAML mapping"


@pytest.mark.parametrize("fixture_name", ["covered", "not_covered", "prior_auth_required"])
def test_stub_fixture_has_covered_field(fixture_name: str) -> None:
    data = yaml.safe_load((_STUBS_ROOT / f"{fixture_name}.yaml").read_text(encoding="utf-8"))
    assert "covered" in data


def test_covered_fixture_covered_true() -> None:
    data = yaml.safe_load((_STUBS_ROOT / "covered.yaml").read_text(encoding="utf-8"))
    assert data["covered"] is True
    assert data["prior_auth_required"] is False


def test_not_covered_fixture_covered_false() -> None:
    data = yaml.safe_load((_STUBS_ROOT / "not_covered.yaml").read_text(encoding="utf-8"))
    assert data["covered"] is False


def test_prior_auth_required_fixture() -> None:
    data = yaml.safe_load((_STUBS_ROOT / "prior_auth_required.yaml").read_text(encoding="utf-8"))
    assert data["covered"] is True
    assert data["prior_auth_required"] is True


# ── case file discovery ───────────────────────────────────────────────────────


def _all_case_files() -> list[Path]:
    return sorted(_CASES_ROOT.rglob("TC-*.yaml"))


def test_exactly_four_case_files() -> None:
    assert len(_all_case_files()) == 4


def test_three_functional_cases() -> None:
    functional = sorted((_CASES_ROOT / "functional").glob("TC-*.yaml"))
    assert len(functional) == 3


def test_one_privacy_case() -> None:
    privacy = sorted((_CASES_ROOT / "privacy").glob("TC-*.yaml"))
    assert len(privacy) == 1


# ── per-case structural validation ───────────────────────────────────────────

_REQUIRED_FIELDS = {"id", "agent", "category", "input", "tool_responses", "expected"}


@pytest.mark.parametrize("case_file", _all_case_files(), ids=lambda p: p.name)
def test_case_has_required_fields(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    missing = _REQUIRED_FIELDS - set(data)
    assert not missing, f"{case_file.name} missing fields: {missing}"


@pytest.mark.parametrize("case_file", _all_case_files(), ids=lambda p: p.name)
def test_case_agent_matches_eligibility(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    assert data["agent"] == "eligibility-v1"


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


@pytest.mark.parametrize("case_file", _all_case_files(), ids=lambda p: p.name)
def test_case_tool_response_references_stub(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    tool_responses = data.get("tool_responses", {})
    assert "check_eligibility" in tool_responses
    stub_ref = tool_responses["check_eligibility"]
    assert isinstance(stub_ref, str), (
        f"{case_file.name}: check_eligibility must reference a stub name"
    )
    assert stub_ref in {"covered", "not_covered", "prior_auth_required"}


# ── privacy case-specific validation ─────────────────────────────────────────


def test_privacy_case_has_must_not_contain() -> None:
    tc004 = yaml.safe_load((_CASES_ROOT / "privacy" / "TC-E-004.yaml").read_text(encoding="utf-8"))
    must_not = tc004["expected"].get("must_not_contain", [])
    assert len(must_not) >= 2, "TC-E-004 must list at least 2 PII patterns to exclude"
