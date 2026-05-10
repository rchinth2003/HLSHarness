"""Unit tests for AdapterScaffolder — no Azure credentials required."""

from __future__ import annotations

import ast

from hlsharness.adapter_scaffolder import AdapterScaffolder, _to_class_name
from hlsharness.manifest import AgentManifest, ManifestTool

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_manifest(
    agent: str = "prior-auth-v1",
    tools: list[ManifestTool] | None = None,
    system_prompt_hint: str = "",
) -> AgentManifest:
    return AgentManifest(
        agent=agent,
        description="Prior authorization agent for insurance approvals",
        categories=["functional", "safety"],
        tools=tools
        or [
            ManifestTool(
                name="check_coverage",
                description="Check insurance coverage",
                parameters={"type": "object", "properties": {"patient_id": {"type": "string"}}},
            ),
            ManifestTool(name="submit_prior_auth", description="Submit a PA request"),
        ],
        thresholds={"functional": 0.8, "safety": 0.9},
        system_prompt_hint=system_prompt_hint,
    )


# ── _to_class_name ────────────────────────────────────────────────────────────


def test_to_class_name_simple() -> None:
    assert _to_class_name("scheduling-v1") == "SchedulingV1Adapter"


def test_to_class_name_multi_word() -> None:
    assert _to_class_name("prior-auth-v1") == "PriorAuthV1Adapter"


def test_to_class_name_single_word() -> None:
    assert _to_class_name("referral") == "ReferralAdapter"


# ── scaffold() ────────────────────────────────────────────────────────────────


def test_scaffold_returns_string() -> None:
    source = AdapterScaffolder().scaffold(_make_manifest())
    assert isinstance(source, str)


def test_scaffold_is_valid_python() -> None:
    source = AdapterScaffolder().scaffold(_make_manifest())
    ast.parse(source)  # raises SyntaxError if invalid


def test_scaffold_contains_class_name() -> None:
    source = AdapterScaffolder().scaffold(_make_manifest("prior-auth-v1"))
    assert "PriorAuthV1Adapter" in source


def test_scaffold_contains_agent_name_in_name_property() -> None:
    source = AdapterScaffolder().scaffold(_make_manifest("prior-auth-v1"))
    assert "'prior-auth-v1'" in source


def test_scaffold_contains_all_tool_names() -> None:
    source = AdapterScaffolder().scaffold(_make_manifest())
    assert "'check_coverage'" in source
    assert "'submit_prior_auth'" in source


def test_scaffold_has_complete_tool_loop() -> None:
    source = AdapterScaffolder().scaffold(_make_manifest())
    assert "tool_simulator.call" in source
    assert "advance_turn" in source
    assert "for _ in range" in source


def test_scaffold_has_exactly_two_todos() -> None:
    source = AdapterScaffolder().scaffold(_make_manifest())
    assert source.count("# TODO") == 2


def test_scaffold_compiles() -> None:
    source = AdapterScaffolder().scaffold(_make_manifest())
    compile(source, "<generated>", "exec")


def test_scaffold_env_var_name_derived_from_agent() -> None:
    source = AdapterScaffolder().scaffold(_make_manifest("prior-auth-v1"))
    assert "AZURE_OPENAI_DEPLOYMENT_PRIOR_AUTH_V1" in source


def test_scaffold_inherits_agent_adapter() -> None:
    source = AdapterScaffolder().scaffold(_make_manifest())
    assert "AgentAdapter" in source


def test_scaffold_uses_system_prompt_hint() -> None:
    manifest = _make_manifest(system_prompt_hint="You are a PA specialist.")
    source = AdapterScaffolder().scaffold(manifest)
    assert "You are a PA specialist." in source


def test_scaffold_falls_back_to_generic_prompt_when_no_hint() -> None:
    manifest = _make_manifest(system_prompt_hint="")
    source = AdapterScaffolder().scaffold(manifest)
    # Should still contain a system_prompt property
    assert "system_prompt" in source


def test_scaffold_empty_tools_list() -> None:
    manifest = _make_manifest(tools=[])
    source = AdapterScaffolder().scaffold(manifest)
    ast.parse(source)  # must still be valid Python
    assert "_TOOLS" in source


def test_scaffold_multiple_agents_produce_different_class_names() -> None:
    src_a = AdapterScaffolder().scaffold(_make_manifest("scheduling-v1"))
    src_b = AdapterScaffolder().scaffold(_make_manifest("prior-auth-v1"))
    assert "SchedulingV1Adapter" in src_a
    assert "PriorAuthV1Adapter" in src_b
    assert "PriorAuthV1Adapter" not in src_a
    assert "SchedulingV1Adapter" not in src_b


def test_scaffold_tool_parameters_are_valid_python() -> None:
    manifest = _make_manifest(
        tools=[
            ManifestTool(
                name="complex_tool",
                description="Tool with nested params",
                parameters={
                    "type": "object",
                    "properties": {
                        "patient_id": {"type": "string"},
                        "urgency": {"type": "string", "enum": ["standard", "urgent"]},
                    },
                    "required": ["patient_id"],
                },
            )
        ]
    )
    source = AdapterScaffolder().scaffold(manifest)
    ast.parse(source)
