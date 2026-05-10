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
    cases = CaseLoader().load(Path("cases"))
    assert len(cases) == 9
    functional = [c for c in cases if c.category == "functional"]
    assert len(functional) == 3
    assert {c.id for c in functional} == {"TC-001", "TC-002", "TC-003"}
    safety = [c for c in cases if c.category == "safety"]
    assert len(safety) == 6
