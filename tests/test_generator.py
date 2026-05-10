"""Unit tests for CaseGenerator — no Azure credentials required."""

from __future__ import annotations

import json
from collections.abc import Callable
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


# ── MafAgentYaml integration ──────────────────────────────────────────────────


def _make_agent_yaml(tools: list[str] | None = None) -> object:
    """Return a MafAgentYaml with the given tool names."""
    from hlsharness.maf_agent import MafAgentYaml, MafToolDef

    tool_list = [
        MafToolDef(
            name=t,
            description=f"Tool {t}",
            parameters={
                "type": "object",
                "properties": {"input": {"type": "string", "description": "input value"}},
                "required": ["input"],
            },
        )
        for t in (tools or ["book_appointment", "search_available_slots"])
    ]
    return MafAgentYaml(
        name="prior-auth-v1",
        description="Prior authorization agent for insurance approvals",
        system_prompt="You are a prior authorization specialist.",
        tools=tool_list,
        x_harness={"categories": ["functional", "equity"], "thresholds": {}, "personas": []},
    )


def _maf_specs(n: int = 1, persona_id: str | None = None) -> list[dict[str, object]]:
    """Return MAF-mode spec dicts with tool_response_scenario + optional persona_id."""
    return [
        {
            "input_content": f"Patient message {i}",
            "expected_outcome": f"Agent books appointment {i}",
            "must_not_contain": [],
            "tool_name": "book_appointment",
            "tool_response_scenario": "confirmed",
            "persona_id": persona_id,
            "metadata": {"language": "english", "insurance": "commercial", "patient_age": 40},
        }
        for i in range(1, n + 1)
    ]


def test_agent_yaml_overrides_tools_param(tmp_path: Path) -> None:
    received: list[str] = []

    def cap_llm(prompt: str, endpoint: str, deployment: str) -> str:
        received.append(prompt)
        return json.dumps(_maf_specs(1))

    gen = CaseGenerator(
        agent="prior-auth-v1",
        output_dir=tmp_path,
        llm_fn=cap_llm,
        agent_yaml=_make_agent_yaml(["book_appointment", "search_available_slots"]),
        tools=["ignored_tool"],
    )
    gen.generate("functional", count=1)

    assert "book_appointment" in received[0]
    assert "search_available_slots" in received[0]
    assert "ignored_tool" not in received[0]


def test_agent_yaml_description_in_prompt(tmp_path: Path) -> None:
    received: list[str] = []

    def cap_llm(prompt: str, endpoint: str, deployment: str) -> str:
        received.append(prompt)
        return json.dumps(_maf_specs(1))

    gen = CaseGenerator(
        agent="prior-auth-v1",
        output_dir=tmp_path,
        llm_fn=cap_llm,
        agent_yaml=_make_agent_yaml(),
    )
    gen.generate("functional", count=1)

    assert "Prior authorization agent for insurance approvals" in received[0]


def test_maf_mode_uses_tool_response_scenario(tmp_path: Path) -> None:
    gen = CaseGenerator(
        agent="prior-auth-v1",
        output_dir=tmp_path,
        llm_fn=_fake_llm(_maf_specs(1)),
        agent_yaml=_make_agent_yaml(),
    )
    (path,) = gen.generate("functional", count=1)
    data = yaml.safe_load(path.read_text())
    assert data["tool_responses"]["book_appointment"] == "confirmed"


def test_maf_mode_equity_includes_persona(tmp_path: Path) -> None:
    specs = _maf_specs(1, persona_id="commercial_english_adult")
    gen = CaseGenerator(
        agent="prior-auth-v1",
        output_dir=tmp_path,
        llm_fn=_fake_llm(specs),
        agent_yaml=_make_agent_yaml(),
    )
    (path,) = gen.generate("equity", count=1)
    data = yaml.safe_load(path.read_text())
    assert data["persona"] == "commercial_english_adult"


def test_maf_mode_no_persona_id_omits_persona_field(tmp_path: Path) -> None:
    specs = _maf_specs(1, persona_id=None)
    gen = CaseGenerator(
        agent="prior-auth-v1",
        output_dir=tmp_path,
        llm_fn=_fake_llm(specs),
        agent_yaml=_make_agent_yaml(),
    )
    (path,) = gen.generate("functional", count=1)
    data = yaml.safe_load(path.read_text())
    assert "persona" not in data


def test_maf_prompt_includes_fixture_scenarios(tmp_path: Path) -> None:
    received: list[str] = []

    def cap_llm(prompt: str, endpoint: str, deployment: str) -> str:
        received.append(prompt)
        return json.dumps(_maf_specs(1))

    stubs_dir = tmp_path / "stubs"
    (stubs_dir / "prior-auth-v1" / "book_appointment").mkdir(parents=True)
    (stubs_dir / "prior-auth-v1" / "book_appointment" / "confirmed.yaml").write_text("status: ok")

    gen = CaseGenerator(
        agent="prior-auth-v1",
        output_dir=tmp_path / "cases",
        llm_fn=cap_llm,
        agent_yaml=_make_agent_yaml(),
        stubs_dir=stubs_dir,
    )
    gen.generate("functional", count=1)

    assert "confirmed" in received[0]


def test_maf_prompt_includes_persona_ids(tmp_path: Path) -> None:
    received: list[str] = []

    def cap_llm(prompt: str, endpoint: str, deployment: str) -> str:
        received.append(prompt)
        return json.dumps(_maf_specs(1, persona_id="commercial_english_adult"))

    personas_dir = tmp_path / "personas"
    personas_dir.mkdir()
    (personas_dir / "commercial_english_adult.yaml").write_text("id: commercial_english_adult")
    (personas_dir / "medicaid_spanish_adult.yaml").write_text("id: medicaid_spanish_adult")

    gen = CaseGenerator(
        agent="prior-auth-v1",
        output_dir=tmp_path / "cases",
        llm_fn=cap_llm,
        agent_yaml=_make_agent_yaml(),
        personas_dir=personas_dir,
    )
    gen.generate("equity", count=1)

    assert "commercial_english_adult" in received[0]
    assert "medicaid_spanish_adult" in received[0]


# ── generate_fixtures() ───────────────────────────────────────────────────────


def _fake_fixture_llm(scenarios: list[dict[str, object]]) -> Callable[[str, str, str], str]:
    def _fn(prompt: str, endpoint: str, deployment: str) -> str:
        return json.dumps(scenarios)

    return _fn


def _default_fixture_scenarios() -> list[dict[str, object]]:
    return [
        {"name": "confirmed", "response": {"status": "confirmed", "confirmation_id": "CONF-001"}},
        {"name": "slot_taken", "response": {"status": "error", "message": "No slots available"}},
    ]


def test_generate_fixtures_writes_yaml_files(tmp_path: Path) -> None:
    stubs_dir = tmp_path / "stubs"
    gen = CaseGenerator(
        agent="prior-auth-v1",
        output_dir=tmp_path / "cases",
        llm_fn=_fake_fixture_llm(_default_fixture_scenarios()),
        agent_yaml=_make_agent_yaml(["book_appointment"]),
    )
    written = gen.generate_fixtures(stubs_dir=stubs_dir)
    assert len(written) == 2
    for p in written:
        assert p.exists()
        assert p.suffix == ".yaml"


def test_generate_fixtures_creates_tool_dirs(tmp_path: Path) -> None:
    stubs_dir = tmp_path / "stubs"
    gen = CaseGenerator(
        agent="prior-auth-v1",
        output_dir=tmp_path / "cases",
        llm_fn=_fake_fixture_llm(_default_fixture_scenarios()),
        agent_yaml=_make_agent_yaml(["book_appointment"]),
    )
    gen.generate_fixtures(stubs_dir=stubs_dir)
    assert (stubs_dir / "prior-auth-v1" / "book_appointment").is_dir()


def test_generate_fixtures_scenario_yaml_is_valid(tmp_path: Path) -> None:
    stubs_dir = tmp_path / "stubs"
    gen = CaseGenerator(
        agent="prior-auth-v1",
        output_dir=tmp_path / "cases",
        llm_fn=_fake_fixture_llm(_default_fixture_scenarios()),
        agent_yaml=_make_agent_yaml(["book_appointment"]),
    )
    gen.generate_fixtures(stubs_dir=stubs_dir)
    confirmed = stubs_dir / "prior-auth-v1" / "book_appointment" / "confirmed.yaml"
    assert confirmed.exists()
    data = yaml.safe_load(confirmed.read_text())
    assert data["status"] == "confirmed"


def test_generate_fixtures_at_least_two_scenarios_per_tool(tmp_path: Path) -> None:
    stubs_dir = tmp_path / "stubs"
    gen = CaseGenerator(
        agent="prior-auth-v1",
        output_dir=tmp_path / "cases",
        llm_fn=_fake_fixture_llm(_default_fixture_scenarios()),
        agent_yaml=_make_agent_yaml(["book_appointment"]),
    )
    gen.generate_fixtures(stubs_dir=stubs_dir)
    tool_dir = stubs_dir / "prior-auth-v1" / "book_appointment"
    fixtures_for_tool = list(tool_dir.glob("*.yaml"))
    assert len(fixtures_for_tool) >= 2


def test_generate_fixtures_covers_multiple_tools(tmp_path: Path) -> None:
    stubs_dir = tmp_path / "stubs"
    gen = CaseGenerator(
        agent="prior-auth-v1",
        output_dir=tmp_path / "cases",
        llm_fn=_fake_fixture_llm(_default_fixture_scenarios()),
        agent_yaml=_make_agent_yaml(["book_appointment", "search_available_slots"]),
    )
    gen.generate_fixtures(stubs_dir=stubs_dir)
    assert (stubs_dir / "prior-auth-v1" / "book_appointment").is_dir()
    assert (stubs_dir / "prior-auth-v1" / "search_available_slots").is_dir()


def test_generate_fixtures_raises_without_agent_yaml(tmp_path: Path) -> None:
    gen = CaseGenerator(
        agent="prior-auth-v1",
        output_dir=tmp_path,
        llm_fn=_fake_fixture_llm([]),
    )
    with pytest.raises(ValueError, match="agent_yaml"):
        gen.generate_fixtures(stubs_dir=tmp_path / "stubs")


def test_generate_fixtures_invalid_json_raises(tmp_path: Path) -> None:
    def bad_llm(prompt: str, endpoint: str, deployment: str) -> str:
        return "not valid json {{"

    gen = CaseGenerator(
        agent="prior-auth-v1",
        output_dir=tmp_path,
        llm_fn=bad_llm,
        agent_yaml=_make_agent_yaml(["book_appointment"]),
    )
    with pytest.raises(RuntimeError, match="invalid JSON"):
        gen.generate_fixtures(stubs_dir=tmp_path / "stubs")
