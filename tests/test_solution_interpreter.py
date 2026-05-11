"""Unit tests for SolutionInterpreter — no Azure credentials required.

Tests cover: solution.yaml structure, threshold inference (min across agents),
topology detection, topology hint in output, and CLI flag wiring.
Follows the fake-LLM injection pattern from test_generator.py.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from hlsharness.solution_interpreter import SolutionInterpreter

# ── helpers ───────────────────────────────────────────────────────────────────


def _fake_llm(critique: str) -> object:
    """Return a callable that always yields the given critique text."""

    def _fn(prompt: str) -> str:
        return critique

    return _fn


def _write_agent_yaml(
    tmp_path: Path,
    name: str,
    *,
    categories: list[str] | None = None,
    thresholds: dict[str, float] | None = None,
    tools: list[str] | None = None,
) -> Path:
    """Write a minimal agent.yaml and return its path."""
    data: dict[str, object] = {
        "name": name,
        "description": f"{name} agent",
        "system_prompt": "You are a helpful agent.",
        "tools": [
            {
                "name": t,
                "description": f"{t} tool",
                "parameters": {"type": "object", "properties": {}, "required": []},
            }
            for t in (tools or [])
        ],
        "x-harness": {
            "categories": categories or ["functional"],
            "thresholds": thresholds or {"functional": 0.8},
            "personas": [],
        },
    }
    p = tmp_path / name / "agent.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return p


# ── solution.yaml structure ───────────────────────────────────────────────────


def test_interpret_returns_tuple_of_strings(tmp_path: Path) -> None:
    path_a = _write_agent_yaml(tmp_path, "agent-a")
    path_b = _write_agent_yaml(tmp_path, "agent-b")
    interp = SolutionInterpreter(llm_fn=_fake_llm("OK"))  # type: ignore[arg-type]
    sol_yaml, critique = interp.interpret([path_a, path_b], "my-solution")
    assert isinstance(sol_yaml, str)
    assert isinstance(critique, str)


def test_solution_yaml_has_required_keys(tmp_path: Path) -> None:
    path_a = _write_agent_yaml(tmp_path, "agent-a")
    interp = SolutionInterpreter(llm_fn=_fake_llm("OK"))  # type: ignore[arg-type]
    sol_yaml, _ = interp.interpret([path_a], "my-solution")
    # Strip comment line before parsing
    yaml_body = "\n".join(line for line in sol_yaml.splitlines() if not line.startswith("#"))
    data = yaml.safe_load(yaml_body)
    assert data["solution"] == "my-solution"
    assert isinstance(data["agents"], list)


def test_solution_name_set_correctly(tmp_path: Path) -> None:
    path_a = _write_agent_yaml(tmp_path, "scheduling-v1")
    interp = SolutionInterpreter(llm_fn=_fake_llm("OK"))  # type: ignore[arg-type]
    sol_yaml, _ = interp.interpret([path_a], "prior-auth-v1")
    yaml_body = "\n".join(line for line in sol_yaml.splitlines() if not line.startswith("#"))
    data = yaml.safe_load(yaml_body)
    assert data["solution"] == "prior-auth-v1"


def test_all_agents_listed_in_yaml(tmp_path: Path) -> None:
    path_a = _write_agent_yaml(tmp_path, "agent-a")
    path_b = _write_agent_yaml(tmp_path, "agent-b")
    path_c = _write_agent_yaml(tmp_path, "agent-c")
    interp = SolutionInterpreter(llm_fn=_fake_llm("OK"))  # type: ignore[arg-type]
    sol_yaml, _ = interp.interpret([path_a, path_b, path_c], "sol")
    yaml_body = "\n".join(line for line in sol_yaml.splitlines() if not line.startswith("#"))
    data = yaml.safe_load(yaml_body)
    names = [a["name"] for a in data["agents"]]
    assert names == ["agent-a", "agent-b", "agent-c"]


def test_stub_false_by_default(tmp_path: Path) -> None:
    path_a = _write_agent_yaml(tmp_path, "agent-a")
    path_b = _write_agent_yaml(tmp_path, "agent-b")
    interp = SolutionInterpreter(llm_fn=_fake_llm("OK"))  # type: ignore[arg-type]
    sol_yaml, _ = interp.interpret([path_a, path_b], "sol")
    yaml_body = "\n".join(line for line in sol_yaml.splitlines() if not line.startswith("#"))
    data = yaml.safe_load(yaml_body)
    assert all(a["stub"] is False for a in data["agents"])


# ── threshold inference ───────────────────────────────────────────────────────


def test_threshold_inference_takes_min_across_agents(tmp_path: Path) -> None:
    """agent-a: functional=0.9; agent-b: functional=0.8 → solution: functional=0.8."""
    path_a = _write_agent_yaml(tmp_path, "agent-a", thresholds={"functional": 0.9, "safety": 0.9})
    path_b = _write_agent_yaml(tmp_path, "agent-b", thresholds={"functional": 0.8, "safety": 1.0})
    interp = SolutionInterpreter(llm_fn=_fake_llm("OK"))  # type: ignore[arg-type]
    sol_yaml, _ = interp.interpret([path_a, path_b], "sol")
    yaml_body = "\n".join(line for line in sol_yaml.splitlines() if not line.startswith("#"))
    data = yaml.safe_load(yaml_body)
    assert data["thresholds"]["functional"] == 0.8
    assert data["thresholds"]["safety"] == 0.9


def test_threshold_categories_sorted_alphabetically(tmp_path: Path) -> None:
    path_a = _write_agent_yaml(
        tmp_path, "agent-a", thresholds={"safety": 0.9, "functional": 0.8, "equity": 0.85}
    )
    interp = SolutionInterpreter(llm_fn=_fake_llm("OK"))  # type: ignore[arg-type]
    sol_yaml, _ = interp.interpret([path_a], "sol")
    yaml_body = "\n".join(line for line in sol_yaml.splitlines() if not line.startswith("#"))
    data = yaml.safe_load(yaml_body)
    keys = list(data["thresholds"].keys())
    assert keys == sorted(keys)


def test_threshold_absent_when_no_agent_has_thresholds(tmp_path: Path) -> None:
    data: dict[str, object] = {
        "name": "agent-a",
        "description": "Agent A",
        "system_prompt": "You are helpful.",
        "tools": [],
        "x-harness": {"categories": ["functional"], "personas": []},
    }
    p = tmp_path / "agent-a" / "agent.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.dump(data), encoding="utf-8")
    interp = SolutionInterpreter(llm_fn=_fake_llm("OK"))  # type: ignore[arg-type]
    sol_yaml, _ = interp.interpret([p], "sol")
    yaml_body = "\n".join(line for line in sol_yaml.splitlines() if not line.startswith("#"))
    parsed = yaml.safe_load(yaml_body)
    assert "thresholds" not in parsed


# ── topology inference ────────────────────────────────────────────────────────


def test_topology_peer_when_no_tool_matches_agent_name(tmp_path: Path) -> None:
    path_a = _write_agent_yaml(tmp_path, "agent-a", tools=["book_appointment"])
    path_b = _write_agent_yaml(tmp_path, "agent-b", tools=["check_eligibility"])
    interp = SolutionInterpreter(llm_fn=_fake_llm("OK"))  # type: ignore[arg-type]
    sol_yaml, _ = interp.interpret([path_a, path_b], "sol")
    assert "peer" in sol_yaml


def test_topology_orchestrator_when_tool_matches_agent_name(tmp_path: Path) -> None:
    """agent-a has tool 'call_agent_b' → agent-a is orchestrator."""
    path_a = _write_agent_yaml(tmp_path, "agent-a", tools=["call_agent_b", "other_tool"])
    path_b = _write_agent_yaml(tmp_path, "agent-b", tools=["do_something"])
    interp = SolutionInterpreter(llm_fn=_fake_llm("OK"))  # type: ignore[arg-type]
    sol_yaml, _ = interp.interpret([path_a, path_b], "sol")
    assert "orchestrator" in sol_yaml
    assert "agent-a" in sol_yaml


def test_topology_hint_present_in_solution_yaml(tmp_path: Path) -> None:
    """topology comment must appear in the YAML output regardless of topology type."""
    path_a = _write_agent_yaml(tmp_path, "agent-a")
    interp = SolutionInterpreter(llm_fn=_fake_llm("OK"))  # type: ignore[arg-type]
    sol_yaml, _ = interp.interpret([path_a], "sol")
    assert "topology" in sol_yaml


# ── critique passthrough ──────────────────────────────────────────────────────


def test_critique_text_returned_from_llm_fn(tmp_path: Path) -> None:
    path_a = _write_agent_yaml(tmp_path, "agent-a")
    expected = "• Threshold for safety looks low.\n• Peer topology confirmed."
    interp = SolutionInterpreter(llm_fn=_fake_llm(expected))  # type: ignore[arg-type]
    _, critique = interp.interpret([path_a], "sol")
    assert critique == expected


def test_critique_prompt_contains_agent_summary(tmp_path: Path) -> None:
    """The prompt passed to llm_fn must mention all agent names."""
    seen_prompts: list[str] = []

    def _capturing_llm(prompt: str) -> str:
        seen_prompts.append(prompt)
        return "OK"

    path_a = _write_agent_yaml(tmp_path, "scheduling-v1")
    path_b = _write_agent_yaml(tmp_path, "billing-v1")
    interp = SolutionInterpreter(llm_fn=_capturing_llm)
    interp.interpret([path_a, path_b], "sol")
    assert len(seen_prompts) == 1
    assert "scheduling-v1" in seen_prompts[0]
    assert "billing-v1" in seen_prompts[0]


# ── CLI flag wiring ───────────────────────────────────────────────────────────


def test_solution_spec_flag_default_none() -> None:
    from hlsharness.__main__ import _build_onboard_parser

    args = _build_onboard_parser().parse_args([])
    assert args.solution_spec is None


def test_solution_name_flag_default_none() -> None:
    from hlsharness.__main__ import _build_onboard_parser

    args = _build_onboard_parser().parse_args([])
    assert args.solution_name is None


def test_solution_spec_accepts_multiple_files() -> None:
    from hlsharness.__main__ import _build_onboard_parser

    args = _build_onboard_parser().parse_args(
        ["--solution-spec", "a.yaml", "b.yaml", "--solution-name", "my-sol"]
    )
    assert args.solution_spec == ["a.yaml", "b.yaml"]
    assert args.solution_name == "my-sol"
