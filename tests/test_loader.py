"""Unit tests for CaseLoader — no Azure credentials required."""

import textwrap
from pathlib import Path

import pytest

from hlsharness.loader import CaseLoader, CaseValidationError

VALID_YAML = textwrap.dedent("""\
    id: TC-TEST
    agent: scheduling-v1
    category: functional
    input:
      messages:
        - role: user
          content: "Book an appointment"
    tool_responses:
      book_appointment:
        status: confirmed
    expected:
      outcome: booked
    metadata:
      patient_age: 35
      language: english
      insurance: commercial
""")


@pytest.fixture()
def case_dir(tmp_path: Path) -> Path:
    d = tmp_path / "cases" / "scheduling-v1" / "functional"
    d.mkdir(parents=True)
    return d


def write_case(directory: Path, filename: str, content: str) -> Path:
    path = directory / filename
    path.write_text(content, encoding="utf-8")
    return path


def test_loads_valid_case(case_dir, tmp_path):
    write_case(case_dir, "TC-TEST.yaml", VALID_YAML)
    loader = CaseLoader()
    cases = loader.load(tmp_path / "cases")
    assert len(cases) == 1
    assert cases[0].id == "TC-TEST"
    assert cases[0].agent == "scheduling-v1"
    assert cases[0].category == "functional"


def test_filters_by_agent(case_dir, tmp_path):
    write_case(case_dir, "TC-TEST.yaml", VALID_YAML)
    loader = CaseLoader()
    assert len(loader.load(tmp_path / "cases", agent="scheduling-v1")) == 1
    assert len(loader.load(tmp_path / "cases", agent="other-agent")) == 0


def test_filters_by_category(case_dir, tmp_path):
    write_case(case_dir, "TC-TEST.yaml", VALID_YAML)
    loader = CaseLoader()
    assert len(loader.load(tmp_path / "cases", category="functional")) == 1
    assert len(loader.load(tmp_path / "cases", category="safety")) == 0


def test_missing_required_field_raises(case_dir, tmp_path):
    bad = VALID_YAML.replace("category: functional\n", "")
    write_case(case_dir, "BAD.yaml", bad)
    with pytest.raises(CaseValidationError, match="category"):
        CaseLoader().load(tmp_path / "cases")


def test_invalid_category_raises(case_dir, tmp_path):
    bad = VALID_YAML.replace("category: functional", "category: unknown")
    write_case(case_dir, "BAD.yaml", bad)
    with pytest.raises(CaseValidationError, match="invalid category"):
        CaseLoader().load(tmp_path / "cases")


def test_malformed_yaml_raises(case_dir, tmp_path):
    write_case(case_dir, "BAD.yaml", "id: [unclosed")
    with pytest.raises(CaseValidationError, match="Malformed YAML"):
        CaseLoader().load(tmp_path / "cases")


def test_missing_messages_key_raises(case_dir, tmp_path):
    bad = VALID_YAML.replace(
        '  messages:\n    - role: user\n      content: "Book an appointment"\n', "  prompt: hi\n"
    )
    write_case(case_dir, "BAD.yaml", bad)
    with pytest.raises(CaseValidationError, match="messages"):
        CaseLoader().load(tmp_path / "cases")


def test_metadata_defaults_to_empty_dict(case_dir, tmp_path):
    no_meta = "\n".join(
        line
        for line in VALID_YAML.splitlines()
        if not line.startswith("metadata")
        and "patient_age" not in line
        and "language" not in line
        and "insurance" not in line
    )
    write_case(case_dir, "TC-NO-META.yaml", no_meta)
    cases = CaseLoader().load(tmp_path / "cases")
    assert cases[0].metadata == {}


def test_loads_real_cases():
    """Smoke test: the committed stub cases load cleanly."""
    cases = CaseLoader().load(Path("cases"), stubs_path=Path("stubs"))
    assert len(cases) > 0
    scheduling = [c for c in cases if c.agent == "scheduling-v1"]
    functional = [c for c in scheduling if c.category == "functional"]
    assert len(functional) == 13
    equity = [c for c in scheduling if c.category == "equity"]
    assert len(equity) == 14
    hitl_routing = [c for c in scheduling if c.category == "hitl_routing"]
    assert len(hitl_routing) == 6


# ── Fixture resolution ────────────────────────────────────────────────────────

FIXTURE_YAML = textwrap.dedent("""\
    id: TC-FIX
    agent: scheduling-v1
    category: functional
    input:
      messages:
        - role: user
          content: "Book an appointment"
    tool_responses:
      search_available_slots: full_slots
    expected:
      outcome: booked
""")


def _write_fixture(stubs_dir: Path, agent: str, tool: str, scenario: str, content: dict) -> None:
    import yaml

    fixture_dir = stubs_dir / agent / tool
    fixture_dir.mkdir(parents=True, exist_ok=True)
    (fixture_dir / f"{scenario}.yaml").write_text(yaml.dump(content), encoding="utf-8")


def test_fixture_string_reference_resolved(tmp_path: Path):
    case_dir = tmp_path / "cases" / "scheduling-v1" / "functional"
    case_dir.mkdir(parents=True)
    write_case(case_dir, "TC-FIX.yaml", FIXTURE_YAML)

    stubs_dir = tmp_path / "stubs"
    _write_fixture(
        stubs_dir, "scheduling-v1", "search_available_slots", "full_slots", {"slots": [1, 2]}
    )

    cases = CaseLoader().load(tmp_path / "cases", stubs_path=stubs_dir)
    assert cases[0].tool_responses["search_available_slots"] == {"slots": [1, 2]}


def test_inline_dict_passes_through_unchanged(case_dir, tmp_path):
    write_case(case_dir, "TC-TEST.yaml", VALID_YAML)
    cases = CaseLoader().load(tmp_path / "cases")
    assert cases[0].tool_responses["book_appointment"] == {"status": "confirmed"}


def test_missing_fixture_raises_validation_error(tmp_path: Path):
    case_dir = tmp_path / "cases" / "scheduling-v1" / "functional"
    case_dir.mkdir(parents=True)
    write_case(case_dir, "TC-FIX.yaml", FIXTURE_YAML)

    stubs_dir = tmp_path / "stubs"
    stubs_dir.mkdir()

    with pytest.raises(CaseValidationError, match="full_slots"):
        CaseLoader().load(tmp_path / "cases", stubs_path=stubs_dir)


def test_empty_tool_responses_loads_without_fixtures(case_dir, tmp_path):
    no_tools = VALID_YAML.replace(
        "tool_responses:\n  book_appointment:\n    status: confirmed\n", "tool_responses: {}\n"
    )
    write_case(case_dir, "TC-EMPTY.yaml", no_tools)
    cases = CaseLoader().load(tmp_path / "cases")
    assert cases[0].tool_responses == {}


def test_multiple_tools_mixed_inline_and_fixture(tmp_path: Path):
    import textwrap

    mixed = textwrap.dedent("""\
        id: TC-MIX
        agent: scheduling-v1
        category: functional
        input:
          messages:
            - role: user
              content: "Mix"
        tool_responses:
          search_available_slots: full_slots
          book_appointment:
            status: confirmed
        expected:
          outcome: booked
    """)
    case_dir = tmp_path / "cases" / "scheduling-v1" / "functional"
    case_dir.mkdir(parents=True)
    write_case(case_dir, "TC-MIX.yaml", mixed)

    stubs_dir = tmp_path / "stubs"
    _write_fixture(
        stubs_dir, "scheduling-v1", "search_available_slots", "full_slots", {"slots": ["A", "B"]}
    )

    cases = CaseLoader().load(tmp_path / "cases", stubs_path=stubs_dir)
    assert cases[0].tool_responses["search_available_slots"] == {"slots": ["A", "B"]}
    assert cases[0].tool_responses["book_appointment"] == {"status": "confirmed"}


def test_real_functional_cases_load_with_fixtures():
    cases = CaseLoader().load(
        Path("cases"), agent="scheduling-v1", category="functional", stubs_path=Path("stubs")
    )
    assert len(cases) == 13
    for case in cases:
        for _tool, response in case.tool_responses.items():
            assert isinstance(response, dict), (
                f"{case.id}: tool_responses values should be dicts after resolution"
            )


def test_real_full_slots_fixture_has_two_slots():
    cases = CaseLoader().load(Path("cases"), category="functional", stubs_path=Path("stubs"))
    tc = next(c for c in cases if c.id == "TC-S-001")
    slots = tc.tool_responses["search_available_slots"].get("slots", [])
    assert len(slots) == 2


def test_real_booking_fixture_resolves_correctly():
    cases = CaseLoader().load(Path("cases"), category="functional", stubs_path=Path("stubs"))
    tc = next(c for c in cases if c.id == "TC-S-002")
    booking = tc.tool_responses.get("book_appointment", {})
    assert booking.get("status") == "confirmed"


def test_real_reschedule_fixture_resolves_correctly():
    cases = CaseLoader().load(Path("cases"), category="functional", stubs_path=Path("stubs"))
    tc = next(c for c in cases if c.id == "TC-S-005")
    reschedule = tc.tool_responses.get("reschedule_appointment", {})
    assert reschedule.get("status") == "rescheduled"


def test_real_waitlist_notified_fixture_resolves_correctly():
    cases = CaseLoader().load(Path("cases"), category="functional", stubs_path=Path("stubs"))
    tc = next(c for c in cases if c.id == "TC-S-008")
    waitlist = tc.tool_responses.get("check_and_notify_waitlist", {})
    assert waitlist.get("status") == "notified"


def test_real_late_cancelled_fixture_has_late_cancellation_flag():
    cases = CaseLoader().load(Path("cases"), category="functional", stubs_path=Path("stubs"))
    tc = next(c for c in cases if c.id == "TC-S-007")
    cancellation = tc.tool_responses.get("cancel_appointment", {})
    assert cancellation.get("late_cancellation") is True


def test_real_privacy_cases_load_with_fixtures():
    cases = CaseLoader().load(
        Path("cases"), agent="eligibility-v1", category="privacy", stubs_path=Path("stubs")
    )
    assert len(cases) == 1
    for case in cases:
        for _tool, response in case.tool_responses.items():
            assert isinstance(response, dict), f"{case.id}: fixture not resolved"
