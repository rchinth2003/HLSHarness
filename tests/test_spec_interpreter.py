"""Unit tests for SpecInterpreter — no Azure credentials required."""

from __future__ import annotations

import json

import pytest

from hlsharness.manifest import AgentManifest, ManifestValidationError
from hlsharness.spec_interpreter import SpecInterpreter

# ── Fake LLM helpers ─────────────────────────────────────────────────────────


def _fake_llm(payload: object) -> object:
    """Return a callable that yields *payload* as JSON."""

    def _fn(prompt: str) -> str:
        return json.dumps(payload)

    return _fn


def _valid_manifest_json() -> dict[str, object]:
    return {
        "agent": "prior-auth-v1",
        "description": "Prior authorization agent",
        "categories": ["functional", "safety"],
        "tools": [
            {
                "name": "check_coverage",
                "description": "Check insurance coverage",
                "parameters": {"type": "object", "properties": {}},
            }
        ],
        "thresholds": {"functional": 0.8, "safety": 0.9},
        "system_prompt_hint": "You are a PA specialist.",
    }


# ── Happy path ────────────────────────────────────────────────────────────────


def test_interpret_returns_agent_manifest() -> None:
    interp = SpecInterpreter(llm_fn=_fake_llm(_valid_manifest_json()))
    result = interp.interpret("some openapi spec text")
    assert isinstance(result, AgentManifest)


def test_interpret_populates_all_fields() -> None:
    interp = SpecInterpreter(llm_fn=_fake_llm(_valid_manifest_json()))
    result = interp.interpret("spec text")

    assert result.agent == "prior-auth-v1"
    assert result.description == "Prior authorization agent"
    assert result.categories == ["functional", "safety"]
    assert len(result.tools) == 1
    assert result.tools[0].name == "check_coverage"
    assert result.thresholds == {"functional": 0.8, "safety": 0.9}
    assert result.system_prompt_hint == "You are a PA specialist."


def test_interpret_passes_spec_text_to_llm() -> None:
    received: list[str] = []

    def capturing_llm(prompt: str) -> str:
        received.append(prompt)
        return json.dumps(_valid_manifest_json())

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
    interp = SpecInterpreter(llm_fn=_fake_llm(_valid_manifest_json()))
    result = interp.interpret(openapi_spec)
    assert result.agent == "prior-auth-v1"


def test_interpret_accepts_plain_english_spec() -> None:
    plain = "An agent that handles prior authorization requests for insurance."
    interp = SpecInterpreter(llm_fn=_fake_llm(_valid_manifest_json()))
    result = interp.interpret(plain)
    assert result.agent == "prior-auth-v1"


# ── Error paths ───────────────────────────────────────────────────────────────


def test_interpret_raises_on_malformed_json() -> None:
    interp = SpecInterpreter(llm_fn=_fake_llm(None))

    def bad_llm(prompt: str) -> str:
        return "not valid json {{"

    interp._llm_fn = bad_llm
    with pytest.raises(RuntimeError, match="invalid JSON"):
        interp.interpret("spec")


def test_interpret_raises_on_json_array_not_object() -> None:
    def array_llm(prompt: str) -> str:
        return json.dumps([{"not": "an object"}])

    interp = SpecInterpreter(llm_fn=array_llm)
    with pytest.raises(RuntimeError, match="expected a JSON object"):
        interp.interpret("spec")


def test_interpret_raises_when_required_field_missing() -> None:
    payload = _valid_manifest_json()
    del payload["thresholds"]
    interp = SpecInterpreter(llm_fn=_fake_llm(payload))
    with pytest.raises(ManifestValidationError, match="thresholds"):
        interp.interpret("spec")


def test_interpret_raises_when_agent_field_missing() -> None:
    payload = _valid_manifest_json()
    del payload["agent"]
    interp = SpecInterpreter(llm_fn=_fake_llm(payload))
    with pytest.raises(ManifestValidationError, match="agent"):
        interp.interpret("spec")
