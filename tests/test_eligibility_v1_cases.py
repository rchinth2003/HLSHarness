"""Structural tests for cases/eligibility-v1 — no agent execution, no LLM calls.

Validates that all case YAMLs are well-formed, agent.yaml has required harness
fields, and all stub fixtures are present and valid YAML.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_CASES_ROOT = Path(__file__).parent.parent / "cases" / "eligibility-v1"
_STUBS_ROOT = Path(__file__).parent.parent / "stubs" / "eligibility-v1" / "check_eligibility"
_AGENT_YAML = _CASES_ROOT / "agent.yaml"

_ALL_STUBS = {
    "covered",
    "not_covered",
    "prior_auth_required",
    "prior_auth_approved",
    "out_of_network",
    "high_deductible",
    "copay_disclosed",
    "prior_auth_denied",
}


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
    assert "regulatory_compliance" in categories
    assert "hitl_routing" in categories


def test_agent_yaml_thresholds() -> None:
    data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    thresholds = data["x-harness"]["thresholds"]
    assert thresholds["functional"] == pytest.approx(0.80)
    assert thresholds["privacy"] == pytest.approx(1.00)
    assert thresholds["regulatory_compliance"] == pytest.approx(0.95)
    assert thresholds["hitl_routing"] == pytest.approx(0.90)


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


def test_eight_stub_fixtures_exist() -> None:
    fixtures = sorted(_STUBS_ROOT.glob("*.yaml"))
    names = {f.stem for f in fixtures}
    assert names == _ALL_STUBS


@pytest.mark.parametrize("fixture_name", sorted(_ALL_STUBS))
def test_stub_fixture_is_valid_yaml(fixture_name: str) -> None:
    fixture_path = _STUBS_ROOT / f"{fixture_name}.yaml"
    data = yaml.safe_load(fixture_path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{fixture_name}.yaml must be a YAML mapping"


@pytest.mark.parametrize("fixture_name", sorted(_ALL_STUBS))
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


def test_prior_auth_approved_fixture() -> None:
    data = yaml.safe_load((_STUBS_ROOT / "prior_auth_approved.yaml").read_text(encoding="utf-8"))
    assert data["covered"] is True
    assert data["prior_auth_status"] == "approved"


def test_prior_auth_denied_fixture() -> None:
    data = yaml.safe_load((_STUBS_ROOT / "prior_auth_denied.yaml").read_text(encoding="utf-8"))
    assert data["prior_auth_status"] == "denied"


def test_out_of_network_fixture() -> None:
    data = yaml.safe_load((_STUBS_ROOT / "out_of_network.yaml").read_text(encoding="utf-8"))
    assert data["covered"] is False
    assert data["network_status"] == "out_of_network"


def test_copay_disclosed_fixture() -> None:
    data = yaml.safe_load((_STUBS_ROOT / "copay_disclosed.yaml").read_text(encoding="utf-8"))
    assert data["covered"] is True
    assert "co_pay" in data


def test_high_deductible_fixture() -> None:
    data = yaml.safe_load((_STUBS_ROOT / "high_deductible.yaml").read_text(encoding="utf-8"))
    assert data["covered"] is True
    assert data["deductible_remaining"] > 0


# ── case file discovery ───────────────────────────────────────────────────────


def _all_case_files() -> list[Path]:
    return sorted(_CASES_ROOT.rglob("TC-*.yaml"))


def test_exactly_fourteen_case_files() -> None:
    assert len(_all_case_files()) == 14


def test_three_functional_cases() -> None:
    functional = sorted((_CASES_ROOT / "functional").glob("TC-*.yaml"))
    assert len(functional) == 3


def test_one_privacy_case() -> None:
    privacy = sorted((_CASES_ROOT / "privacy").glob("TC-*.yaml"))
    assert len(privacy) == 1


def test_six_regulatory_compliance_cases() -> None:
    reg = sorted((_CASES_ROOT / "regulatory_compliance").glob("TC-*.yaml"))
    assert len(reg) == 6


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
def test_case_tool_response_references_known_stub(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    tool_responses = data.get("tool_responses", {})
    assert "check_eligibility" in tool_responses
    stub_ref = tool_responses["check_eligibility"]
    assert isinstance(stub_ref, str), (
        f"{case_file.name}: check_eligibility must reference a stub name"
    )
    assert stub_ref in _ALL_STUBS, f"{case_file.name}: unknown stub '{stub_ref}'"


# ── privacy case-specific validation ─────────────────────────────────────────


def test_privacy_case_has_must_not_contain() -> None:
    tc004 = yaml.safe_load((_CASES_ROOT / "privacy" / "TC-E-004.yaml").read_text(encoding="utf-8"))
    must_not = tc004["expected"].get("must_not_contain", [])
    assert len(must_not) >= 2, "TC-E-004 must list at least 2 PII patterns to exclude"


# ── regulatory_compliance case-specific validation ────────────────────────────

_VALID_SEVERITY_LEVELS = {"HIGH", "MEDIUM"}


@pytest.mark.parametrize(
    "case_file",
    sorted((_CASES_ROOT / "regulatory_compliance").glob("TC-*.yaml")),
    ids=lambda p: p.name,
)
def test_regulatory_compliance_case_has_severity(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    severity = data["expected"].get("severity")
    assert severity in _VALID_SEVERITY_LEVELS, f"{case_file.name}: invalid severity '{severity}'"


@pytest.mark.parametrize(
    "case_file",
    sorted((_CASES_ROOT / "regulatory_compliance").glob("TC-*.yaml")),
    ids=lambda p: p.name,
)
def test_regulatory_compliance_case_has_outcome(case_file: Path) -> None:
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
def test_hitl_case_reason_code_is_eligibility_failure(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    reason = data["expected"].get("reason_code")
    assert reason == "eligibility_failure", (
        f"{case_file.name}: expected reason_code 'eligibility_failure', got '{reason}'"
    )
