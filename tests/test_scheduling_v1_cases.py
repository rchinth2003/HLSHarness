"""Structural tests for cases/scheduling-v1 — no agent execution, no LLM calls.

Validates that all case YAMLs are well-formed, agent.yaml has required harness
fields, and all stub fixtures are present and valid YAML.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_CASES_ROOT = Path(__file__).parent.parent / "cases" / "scheduling-v1"
_STUBS_SLOTS = Path(__file__).parent.parent / "stubs" / "scheduling-v1" / "search_available_slots"
_STUBS_BOOK = Path(__file__).parent.parent / "stubs" / "scheduling-v1" / "book_appointment"
_PERSONAS_ROOT = Path(__file__).parent.parent / "personas"
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
    assert data["name"] == "scheduling-v1"


def test_agent_yaml_model() -> None:
    data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    assert data.get("model") == "gpt-4o-mini"


def test_agent_yaml_categories() -> None:
    data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    categories = data["x-harness"]["categories"]
    assert "functional" in categories
    assert "equity" in categories


def test_agent_yaml_thresholds() -> None:
    data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    thresholds = data["x-harness"]["thresholds"]
    assert thresholds["functional"] == pytest.approx(0.80)
    assert thresholds["equity"] == pytest.approx(0.90)


def test_agent_yaml_has_search_available_slots_tool() -> None:
    data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    tool_names = [t["name"] for t in data.get("tools", [])]
    assert "search_available_slots" in tool_names


def test_agent_yaml_has_book_appointment_tool() -> None:
    data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    tool_names = [t["name"] for t in data.get("tools", [])]
    assert "book_appointment" in tool_names


def test_search_available_slots_required_params() -> None:
    data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    tool = next(t for t in data["tools"] if t["name"] == "search_available_slots")
    required = tool["parameters"]["required"]
    assert "provider_id" in required
    assert "date_range_start" in required
    assert "date_range_end" in required


def test_book_appointment_required_params() -> None:
    data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    tool = next(t for t in data["tools"] if t["name"] == "book_appointment")
    required = tool["parameters"]["required"]
    assert "slot_id" in required
    assert "patient_id" in required


def test_agent_yaml_has_ten_personas() -> None:
    data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    personas = data["x-harness"]["personas"]
    assert len(personas) == 10


def test_agent_yaml_system_prompt_mentions_no_available_slots() -> None:
    data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    assert "no_available_slots" in data["system_prompt"]


# ── stub fixtures ─────────────────────────────────────────────────────────────


def test_stub_slot_found_exists() -> None:
    assert (_STUBS_SLOTS / "full_slots.yaml").exists()


def test_stub_no_availability_exists() -> None:
    assert (_STUBS_SLOTS / "no_availability.yaml").exists()


def test_stub_multi_provider_exists() -> None:
    assert (_STUBS_SLOTS / "multi_provider.yaml").exists()


def test_stub_book_confirmed_exists() -> None:
    assert (_STUBS_BOOK / "confirmed.yaml").exists()


def test_stub_full_slots_has_slots_list() -> None:
    data = yaml.safe_load((_STUBS_SLOTS / "full_slots.yaml").read_text(encoding="utf-8"))
    assert "slots" in data
    assert len(data["slots"]) >= 1


def test_stub_no_availability_is_empty_list() -> None:
    data = yaml.safe_load((_STUBS_SLOTS / "no_availability.yaml").read_text(encoding="utf-8"))
    assert data.get("slots") == []


def test_stub_multi_provider_has_multiple_providers() -> None:
    data = yaml.safe_load((_STUBS_SLOTS / "multi_provider.yaml").read_text(encoding="utf-8"))
    providers = {s["provider"] for s in data["slots"]}
    assert len(providers) >= 2


def test_stub_book_confirmed_has_confirmation_id() -> None:
    data = yaml.safe_load((_STUBS_BOOK / "confirmed.yaml").read_text(encoding="utf-8"))
    assert "confirmation_id" in data
    assert data.get("status") == "confirmed"


# ── case file discovery ───────────────────────────────────────────────────────


def _all_case_files() -> list[Path]:
    return sorted(_CASES_ROOT.rglob("TC-*.yaml"))


def _functional_case_files() -> list[Path]:
    return sorted((_CASES_ROOT / "functional").glob("TC-*.yaml"))


def _equity_case_files() -> list[Path]:
    return sorted((_CASES_ROOT / "equity").glob("TC-*.yaml"))


def _hitl_routing_case_files() -> list[Path]:
    return sorted((_CASES_ROOT / "hitl_routing").glob("TC-*.yaml"))


def test_ten_functional_cases() -> None:
    assert len(_functional_case_files()) == 11


def test_fourteen_equity_cases() -> None:
    assert len(_equity_case_files()) == 14


def test_four_hitl_routing_cases() -> None:
    assert len(_hitl_routing_case_files()) == 5


def test_twentyeight_total_cases() -> None:
    assert len(_all_case_files()) == 30


# ── per-case structural validation ───────────────────────────────────────────

_REQUIRED_FIELDS = {"id", "agent", "category", "input", "tool_responses", "expected", "metadata"}


@pytest.mark.parametrize("case_file", _all_case_files(), ids=lambda p: p.name)
def test_case_has_required_fields(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    missing = _REQUIRED_FIELDS - set(data)
    assert not missing, f"{case_file.name} missing fields: {missing}"


@pytest.mark.parametrize("case_file", _all_case_files(), ids=lambda p: p.name)
def test_case_agent_matches_scheduling(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    assert data["agent"] == "scheduling-v1"


@pytest.mark.parametrize("case_file", _all_case_files(), ids=lambda p: p.name)
def test_case_category_matches_directory(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    expected_category = case_file.parent.name
    assert data["category"] == expected_category


@pytest.mark.parametrize("case_file", _all_case_files(), ids=lambda p: p.name)
def test_case_metadata_has_required_keys(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    meta = data.get("metadata", {})
    for key in ("scenario", "patient_age", "language", "insurance"):
        assert key in meta, f"{case_file.name} metadata missing: {key}"


@pytest.mark.parametrize("case_file", _all_case_files(), ids=lambda p: p.name)
def test_case_tool_responses_reference_valid_stubs(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    tool_responses = data.get("tool_responses", {})
    for tool_name, fixture_name in tool_responses.items():
        stub_dir = Path(__file__).parent.parent / "stubs" / "scheduling-v1" / tool_name
        stub_file = stub_dir / f"{fixture_name}.yaml"
        assert stub_file.exists(), f"{case_file.name}: stub not found: {stub_file}"


# ── equity case validation ────────────────────────────────────────────────────


@pytest.mark.parametrize("case_file", _equity_case_files(), ids=lambda p: p.name)
def test_equity_case_references_known_persona(case_file: Path) -> None:
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    persona_id = data.get("persona")
    assert persona_id is not None, f"{case_file.name} missing persona field"
    persona_file = _PERSONAS_ROOT / f"{persona_id}.yaml"
    assert persona_file.exists(), f"{case_file.name}: persona not found: {persona_file}"


def test_equity_cases_cover_all_agent_personas() -> None:
    agent_data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    declared_personas = set(agent_data["x-harness"]["personas"])
    case_personas = set()
    for cf in _equity_case_files():
        data = yaml.safe_load(cf.read_text(encoding="utf-8"))
        if p := data.get("persona"):
            case_personas.add(p)
    assert declared_personas == case_personas, (
        f"Persona mismatch — declared: {declared_personas}, covered: {case_personas}"
    )


# ── HITL escalation functional case ──────────────────────────────────────────


def test_tc_s_003_expects_hitl_escalation() -> None:
    case_file = _CASES_ROOT / "functional" / "TC-S-003.yaml"
    data = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    expected = data["expected"]
    assert expected.get("escalate") is True
    assert expected.get("reason") == "no_available_slots"
    assert expected.get("confidence") == pytest.approx(1.0)


def test_scheduling_agent_declares_verify_patient_identity_tool():
    data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    tool_names = {t["name"] for t in data["tools"]}
    assert "verify_patient_identity" in tool_names

def test_scheduling_agent_prompt_requires_verify_before_get_patient_record():
    data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    prompt = data["system_prompt"]
    assert "verify_patient_identity" in prompt
    assert "before" in prompt.lower() and "get_patient_record" in prompt


def test_scheduling_agent_declares_match_providers_tool():
    data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    tool_names = {t["name"] for t in data["tools"]}
    assert "match_providers" in tool_names


def test_scheduling_agent_prompt_calls_match_providers_before_search():
    data = yaml.safe_load(_AGENT_YAML.read_text(encoding="utf-8"))
    prompt = data["system_prompt"]
    assert "match_providers" in prompt
    assert "search_available_slots" in prompt
