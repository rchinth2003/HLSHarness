"""Unit tests for SpecInterpreter — no Azure credentials required."""

from __future__ import annotations

import json

import pytest

from hlsharness.maf_agent import MafAgentYaml, MafAgentYamlError
from hlsharness.spec_interpreter import SpecInterpreter

# ── Fake LLM helpers ─────────────────────────────────────────────────────────


def _fake_llm(payload: object) -> object:
    """Return a callable that yields *payload* as JSON."""

    def _fn(prompt: str) -> str:
        return json.dumps(payload)

    return _fn


def _valid_maf_yaml_json() -> dict[str, object]:
    return {
        "name": "prior-auth-v1",
        "description": "Prior authorization agent",
        "system_prompt": "You are a prior authorization specialist. Help users with insurance approvals.",
        "tools": [
            {
                "name": "check_coverage",
                "description": "Check insurance coverage for a procedure",
                "parameters": {
                    "type": "object",
                    "properties": {"procedure_code": {"type": "string", "description": "CPT code"}},
                    "required": ["procedure_code"],
                },
            }
        ],
        "x-harness": {
            "categories": ["functional", "safety"],
            "thresholds": {"functional": 0.8, "safety": 0.9},
            "personas": [],
        },
    }


# ── Happy path ────────────────────────────────────────────────────────────────


def test_interpret_returns_maf_agent_yaml() -> None:
    interp = SpecInterpreter(llm_fn=_fake_llm(_valid_maf_yaml_json()))
    result = interp.interpret("some openapi spec text")
    assert isinstance(result, MafAgentYaml)


def test_interpret_populates_all_fields() -> None:
    interp = SpecInterpreter(llm_fn=_fake_llm(_valid_maf_yaml_json()))
    result = interp.interpret("spec text")

    assert result.name == "prior-auth-v1"
    assert result.description == "Prior authorization agent"
    assert "prior authorization" in result.system_prompt.lower()
    assert len(result.tools) == 1
    assert result.tools[0].name == "check_coverage"
    assert result.x_harness["categories"] == ["functional", "safety"]
    assert result.x_harness["thresholds"] == {"functional": 0.8, "safety": 0.9}
    assert result.x_harness["personas"] == []


def test_interpret_populates_x_harness_block() -> None:
    interp = SpecInterpreter(llm_fn=_fake_llm(_valid_maf_yaml_json()))
    result = interp.interpret("spec text")
    assert "categories" in result.x_harness
    assert "thresholds" in result.x_harness
    assert "personas" in result.x_harness


def test_interpret_passes_spec_text_to_llm() -> None:
    received: list[str] = []

    def capturing_llm(prompt: str) -> str:
        received.append(prompt)
        return json.dumps(_valid_maf_yaml_json())

    SpecInterpreter(llm_fn=capturing_llm).interpret("unique spec content xyz")
    assert len(received) == 1
    assert "unique spec content xyz" in received[0]


def test_interpret_accepts_openapi_shaped_spec() -> None:
    openapi_spec = json.dumps(
        {
            "openapi": "3.0.0",
            "info": {"title": "Prior Auth API", "version": "1.0"},
            "paths": {"/check": {"post": {"operationId": "check_coverage"}}},
        }
    )
    interp = SpecInterpreter(llm_fn=_fake_llm(_valid_maf_yaml_json()))
    result = interp.interpret(openapi_spec)
    assert result.name == "prior-auth-v1"


def test_interpret_accepts_plain_english_spec() -> None:
    plain = "An agent that handles prior authorization requests for insurance."
    interp = SpecInterpreter(llm_fn=_fake_llm(_valid_maf_yaml_json()))
    result = interp.interpret(plain)
    assert result.name == "prior-auth-v1"


def test_interpret_tool_parameters_preserved() -> None:
    interp = SpecInterpreter(llm_fn=_fake_llm(_valid_maf_yaml_json()))
    result = interp.interpret("spec")
    tool = result.tools[0]
    assert "properties" in tool.parameters
    assert "procedure_code" in tool.parameters["properties"]


# ── Error paths ───────────────────────────────────────────────────────────────


def test_interpret_raises_on_malformed_json() -> None:
    def bad_llm(prompt: str) -> str:
        return "not valid json {{"

    interp = SpecInterpreter(llm_fn=bad_llm)
    with pytest.raises(RuntimeError, match="invalid JSON"):
        interp.interpret("spec")


def test_interpret_raises_on_json_array_not_object() -> None:
    def array_llm(prompt: str) -> str:
        return json.dumps([{"not": "an object"}])

    interp = SpecInterpreter(llm_fn=array_llm)
    with pytest.raises(RuntimeError, match="expected a JSON object"):
        interp.interpret("spec")


def test_interpret_raises_when_x_harness_missing() -> None:
    payload = _valid_maf_yaml_json()
    del payload["x-harness"]
    interp = SpecInterpreter(llm_fn=_fake_llm(payload))
    with pytest.raises(MafAgentYamlError, match="x-harness"):
        interp.interpret("spec")


def test_interpret_raises_when_name_missing() -> None:
    payload = _valid_maf_yaml_json()
    del payload["name"]
    interp = SpecInterpreter(llm_fn=_fake_llm(payload))
    with pytest.raises(MafAgentYamlError, match="name"):
        interp.interpret("spec")


def test_interpret_raises_when_system_prompt_missing() -> None:
    payload = _valid_maf_yaml_json()
    del payload["system_prompt"]
    interp = SpecInterpreter(llm_fn=_fake_llm(payload))
    with pytest.raises(MafAgentYamlError, match="system_prompt"):
        interp.interpret("spec")


# ── Phase 2: critique ─────────────────────────────────────────────────────────


def test_critique_calls_llm_with_yaml_text() -> None:
    received: list[str] = []

    def capturing_llm(prompt: str) -> str:
        received.append(prompt)
        return "Critique: add error scenarios for check_coverage."

    interp = SpecInterpreter(llm_fn=capturing_llm)
    interp.critique("name: prior-auth-v1\ntools: []")
    assert len(received) == 1
    assert "prior-auth-v1" in received[0]


def test_critique_returns_llm_text() -> None:
    expected = "1. Missing error paths: check_coverage lacks not_found scenario."

    def critique_llm(prompt: str) -> str:
        return expected

    interp = SpecInterpreter(llm_fn=critique_llm)
    result = interp.critique("name: prior-auth-v1")
    assert result == expected


def test_critique_output_contains_behavioral_reasoning() -> None:
    canned = (
        "1. Missing error-path tool responses: check_coverage has no 'not_found' scenario.\n"
        "2. Ambiguous parameter schemas: procedure_code lacks enum constraints.\n"
        "3. Threshold analysis: safety=0.9 is appropriate for clinical context.\n"
        "4. Tool descriptions: 'Check insurance coverage' is too brief."
    )

    interp = SpecInterpreter(llm_fn=lambda _prompt: canned)
    result = interp.critique("name: prior-auth-v1\ntools:\n  - name: check_coverage")
    assert "error" in result.lower()
    assert "threshold" in result.lower()
    assert "parameter" in result.lower()


def test_critique_uses_same_llm_fn_as_interpret() -> None:
    calls: list[str] = []

    def recording_llm(prompt: str) -> str:
        calls.append(prompt)
        if calls and "critique" in prompt.lower() or "Critique" in prompt:
            return "Behavioral critique text."
        return json.dumps(_valid_maf_yaml_json())

    interp = SpecInterpreter(llm_fn=recording_llm)
    interp.interpret("spec")
    interp.critique("name: prior-auth-v1")
    assert len(calls) == 2
