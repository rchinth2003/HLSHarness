"""Unit tests for CaseGenerator — no Azure credentials required."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from hlsharness.generator import CaseGenerator


def _fake_llm(specs: list[dict[str, object]]) -> object:
    """Return a callable that always yields the given specs as JSON."""

    def _fn(prompt: str, endpoint: str, deployment: str) -> str:
        return json.dumps(specs)

    return _fn


def _default_specs(n: int = 2) -> list[dict[str, object]]:
    return [
        {
            "input_content": f"Patient message {i}",
            "expected_outcome": f"Agent books appointment {i}",
            "must_not_contain": [],
            "tool_name": "book_appointment",
            "tool_response": {"confirmation_id": f"CONF-{i:03d}", "status": "confirmed"},
            "metadata": {"language": "english", "insurance": "commercial", "patient_age": 35 + i},
        }
        for i in range(1, n + 1)
    ]


# ── generate() ────────────────────────────────────────────────────────────────


def test_generate_writes_yaml_files(tmp_path: Path) -> None:
    gen = CaseGenerator(
        agent="scheduling-v1",
        output_dir=tmp_path,
        llm_fn=_fake_llm(_default_specs(3)),
    )
    paths = gen.generate("functional", count=3)
    assert len(paths) == 3
    for p in paths:
        assert p.exists()
        assert p.suffix == ".yaml"


def test_generated_yaml_is_valid(tmp_path: Path) -> None:
    gen = CaseGenerator(
        agent="scheduling-v1",
        output_dir=tmp_path,
        llm_fn=_fake_llm(_default_specs(1)),
    )
    (path,) = gen.generate("functional", count=1)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["agent"] == "scheduling-v1"
    assert data["category"] == "functional"
    assert "input" in data and "messages" in data["input"]
    assert "expected" in data
    assert "tool_responses" in data


def test_generated_case_id_format(tmp_path: Path) -> None:
    gen = CaseGenerator(
        agent="scheduling-v1",
        output_dir=tmp_path,
        llm_fn=_fake_llm(_default_specs(1)),
    )
    (path,) = gen.generate("functional", count=1)
    assert path.name == "TC-001.yaml"
    data = yaml.safe_load(path.read_text())
    assert data["id"] == "TC-001"


def test_numbering_skips_existing(tmp_path: Path) -> None:
    out_dir = tmp_path / "scheduling-v1" / "functional"
    out_dir.mkdir(parents=True)
    (out_dir / "TC-001.yaml").write_text("placeholder")

    gen = CaseGenerator(
        agent="scheduling-v1",
        output_dir=tmp_path,
        llm_fn=_fake_llm(_default_specs(1)),
    )
    (path,) = gen.generate("functional", count=1)
    assert path.name == "TC-002.yaml"


def test_numbering_fills_gaps(tmp_path: Path) -> None:
    out_dir = tmp_path / "scheduling-v1" / "functional"
    out_dir.mkdir(parents=True)
    (out_dir / "TC-001.yaml").write_text("placeholder")
    (out_dir / "TC-003.yaml").write_text("placeholder")

    gen = CaseGenerator(
        agent="scheduling-v1",
        output_dir=tmp_path,
        llm_fn=_fake_llm(_default_specs(1)),
    )
    (path,) = gen.generate("functional", count=1)
    assert path.name == "TC-002.yaml"


def test_output_dir_created_automatically(tmp_path: Path) -> None:
    gen = CaseGenerator(
        agent="new-agent",
        output_dir=tmp_path,
        llm_fn=_fake_llm(_default_specs(1)),
    )
    gen.generate("safety", count=1)
    assert (tmp_path / "new-agent" / "safety").is_dir()


def test_count_limits_output(tmp_path: Path) -> None:
    # LLM returns 5 specs but we only asked for 2
    gen = CaseGenerator(
        agent="scheduling-v1",
        output_dir=tmp_path,
        llm_fn=_fake_llm(_default_specs(5)),
    )
    paths = gen.generate("functional", count=2)
    assert len(paths) == 2


def test_tool_responses_populated(tmp_path: Path) -> None:
    gen = CaseGenerator(
        agent="scheduling-v1",
        output_dir=tmp_path,
        llm_fn=_fake_llm(_default_specs(1)),
    )
    (path,) = gen.generate("functional", count=1)
    data = yaml.safe_load(path.read_text())
    assert "book_appointment" in data["tool_responses"]
    assert data["tool_responses"]["book_appointment"]["status"] == "confirmed"


def test_no_tool_name_leaves_empty_responses(tmp_path: Path) -> None:
    specs = [
        {
            "input_content": "Hello",
            "expected_outcome": "Greet patient",
            "must_not_contain": [],
            "tool_name": None,
            "tool_response": None,
            "metadata": {"language": "english", "insurance": "commercial", "patient_age": 30},
        }
    ]
    gen = CaseGenerator(
        agent="scheduling-v1",
        output_dir=tmp_path,
        llm_fn=_fake_llm(specs),
    )
    (path,) = gen.generate("functional", count=1)
    data = yaml.safe_load(path.read_text())
    assert data["tool_responses"] == {}


def test_must_not_contain_written(tmp_path: Path) -> None:
    specs = [
        {
            "input_content": "My SSN is 123-45-6789",
            "expected_outcome": "Agent must not echo PHI",
            "must_not_contain": ["123-45-6789"],
            "tool_name": None,
            "tool_response": None,
            "metadata": {"language": "english", "insurance": "commercial", "patient_age": 45},
        }
    ]
    gen = CaseGenerator(
        agent="scheduling-v1",
        output_dir=tmp_path,
        llm_fn=_fake_llm(specs),
    )
    (path,) = gen.generate("privacy", count=1)
    data = yaml.safe_load(path.read_text())
    assert "123-45-6789" in data["expected"]["must_not_contain"]


def test_metadata_written(tmp_path: Path) -> None:
    gen = CaseGenerator(
        agent="scheduling-v1",
        output_dir=tmp_path,
        llm_fn=_fake_llm(_default_specs(1)),
    )
    (path,) = gen.generate("functional", count=1)
    data = yaml.safe_load(path.read_text())
    assert data["metadata"]["language"] == "english"
    assert data["metadata"]["insurance"] == "commercial"


# ── validation errors ─────────────────────────────────────────────────────────


def test_invalid_category_raises(tmp_path: Path) -> None:
    gen = CaseGenerator(
        agent="scheduling-v1",
        output_dir=tmp_path,
        llm_fn=_fake_llm([]),
    )
    with pytest.raises(ValueError, match="Invalid category"):
        gen.generate("bogus", count=1)


def test_count_zero_raises(tmp_path: Path) -> None:
    gen = CaseGenerator(
        agent="scheduling-v1",
        output_dir=tmp_path,
        llm_fn=_fake_llm([]),
    )
    with pytest.raises(ValueError, match="count must be between"):
        gen.generate("functional", count=0)


def test_count_too_large_raises(tmp_path: Path) -> None:
    gen = CaseGenerator(
        agent="scheduling-v1",
        output_dir=tmp_path,
        llm_fn=_fake_llm([]),
    )
    with pytest.raises(ValueError, match="count must be between"):
        gen.generate("functional", count=51)


# ── _parse_specs ──────────────────────────────────────────────────────────────


def test_parse_specs_from_plain_array(tmp_path: Path) -> None:
    gen = CaseGenerator("x", tmp_path, llm_fn=_fake_llm([]))
    specs = gen._parse_specs(json.dumps([{"a": 1}, {"b": 2}]))
    assert len(specs) == 2


def test_parse_specs_from_wrapped_object(tmp_path: Path) -> None:
    gen = CaseGenerator("x", tmp_path, llm_fn=_fake_llm([]))
    raw = json.dumps({"cases": [{"a": 1}]})
    specs = gen._parse_specs(raw)
    assert len(specs) == 1


def test_parse_specs_invalid_json_raises(tmp_path: Path) -> None:
    gen = CaseGenerator("x", tmp_path, llm_fn=_fake_llm([]))
    with pytest.raises(RuntimeError, match="invalid JSON"):
        gen._parse_specs("not json at all")


def test_parse_specs_non_array_raises(tmp_path: Path) -> None:
    gen = CaseGenerator("x", tmp_path, llm_fn=_fake_llm([]))
    with pytest.raises(RuntimeError, match="Expected a JSON array"):
        gen._parse_specs('"just a string"')


# ── _next_id ──────────────────────────────────────────────────────────────────


def test_next_id_starts_at_001(tmp_path: Path) -> None:
    out_dir = tmp_path / "scheduling-v1" / "functional"
    out_dir.mkdir(parents=True)
    gen = CaseGenerator("scheduling-v1", tmp_path, llm_fn=_fake_llm([]))
    assert gen._next_id(out_dir) == "TC-001"


def test_next_id_sequential(tmp_path: Path) -> None:
    out_dir = tmp_path / "scheduling-v1" / "functional"
    out_dir.mkdir(parents=True)
    for i in range(1, 4):
        (out_dir / f"TC-{i:03d}.yaml").write_text("")
    gen = CaseGenerator("scheduling-v1", tmp_path, llm_fn=_fake_llm([]))
    assert gen._next_id(out_dir) == "TC-004"


# ── Manifest enrichment (tools + agent_description) ───────────────────────────


def test_tools_injected_into_prompt(tmp_path: Path) -> None:
    received_prompts: list[str] = []

    def capturing_llm(prompt: str, endpoint: str, deployment: str) -> str:
        received_prompts.append(prompt)
        return json.dumps(_default_specs(1))

    gen = CaseGenerator(
        agent="prior-auth-v1",
        output_dir=tmp_path,
        llm_fn=capturing_llm,
        tools=["check_coverage", "submit_prior_auth"],
    )
    gen.generate("functional", count=1)

    assert len(received_prompts) == 1
    assert "check_coverage" in received_prompts[0]
    assert "submit_prior_auth" in received_prompts[0]


def test_agent_description_injected_into_prompt(tmp_path: Path) -> None:
    received_prompts: list[str] = []

    def capturing_llm(prompt: str, endpoint: str, deployment: str) -> str:
        received_prompts.append(prompt)
        return json.dumps(_default_specs(1))

    gen = CaseGenerator(
        agent="prior-auth-v1",
        output_dir=tmp_path,
        llm_fn=capturing_llm,
        agent_description="Prior authorization agent for insurance approvals",
    )
    gen.generate("functional", count=1)

    assert len(received_prompts) == 1
    assert "Prior authorization agent for insurance approvals" in received_prompts[0]


def test_no_tools_uses_default_tool_names(tmp_path: Path) -> None:
    received_prompts: list[str] = []

    def capturing_llm(prompt: str, endpoint: str, deployment: str) -> str:
        received_prompts.append(prompt)
        return json.dumps(_default_specs(1))

    gen = CaseGenerator(
        agent="scheduling-v1",
        output_dir=tmp_path,
        llm_fn=capturing_llm,
    )
    gen.generate("functional", count=1)

    assert "book_appointment" in received_prompts[0]


def test_no_agent_description_omits_description_line(tmp_path: Path) -> None:
    received_prompts: list[str] = []

    def capturing_llm(prompt: str, endpoint: str, deployment: str) -> str:
        received_prompts.append(prompt)
        return json.dumps(_default_specs(1))

    gen = CaseGenerator(
        agent="scheduling-v1",
        output_dir=tmp_path,
        llm_fn=capturing_llm,
    )
    gen.generate("functional", count=1)

    assert "Description:" not in received_prompts[0]


def test_generated_yaml_loadable_by_case_loader(tmp_path: Path) -> None:
    from hlsharness.loader import CaseLoader

    gen = CaseGenerator(
        agent="scheduling-v1",
        output_dir=tmp_path,
        llm_fn=_fake_llm(_default_specs(1)),
        tools=["book_appointment"],
    )
    gen.generate("functional", count=1)

    cases = CaseLoader().load(tmp_path, agent="scheduling-v1")
    assert len(cases) == 1
    assert cases[0].agent == "scheduling-v1"
