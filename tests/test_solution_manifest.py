"""Unit tests for SolutionManifest — solution.yaml loader and validator."""

from __future__ import annotations

from pathlib import Path

import pytest

from hlsharness.controller import CaseValidationError
from hlsharness.solution_manifest import AgentEntry, SolutionManifest


def _write_manifest(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "solution.yaml"
    p.write_text(content, encoding="utf-8")
    return p


def _scaffold_agent(cases_path: Path, name: str) -> None:
    agent_dir = cases_path / name
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "agent.yaml").write_text(f"name: {name}\n", encoding="utf-8")


def _scaffold_stubs(stubs_path: Path, name: str) -> None:
    stub_dir = stubs_path / name / "check_availability"
    stub_dir.mkdir(parents=True, exist_ok=True)
    (stub_dir / "default.yaml").write_text("result: ok\n", encoding="utf-8")


# ── SolutionManifest.load ─────────────────────────────────────────────────────


def test_load_parses_solution_name(tmp_path: Path) -> None:
    p = _write_manifest(
        tmp_path,
        "solution: prior-auth-v1\nagents:\n  - name: scheduling-v1\n    stub: false\n",
    )
    m = SolutionManifest.load(p)
    assert m.solution == "prior-auth-v1"


def test_load_parses_agents(tmp_path: Path) -> None:
    p = _write_manifest(
        tmp_path,
        "solution: s\nagents:\n  - name: a1\n    stub: false\n  - name: a2\n    stub: true\n",
    )
    m = SolutionManifest.load(p)
    assert len(m.agents) == 2
    assert m.agents[0] == AgentEntry(name="a1", stub=False)
    assert m.agents[1] == AgentEntry(name="a2", stub=True)


def test_load_stub_defaults_to_false(tmp_path: Path) -> None:
    p = _write_manifest(tmp_path, "solution: s\nagents:\n  - name: a1\n")
    m = SolutionManifest.load(p)
    assert m.agents[0].stub is False


def test_load_parses_thresholds(tmp_path: Path) -> None:
    p = _write_manifest(
        tmp_path,
        "solution: s\nagents:\n  - name: a1\nthresholds:\n  functional: 0.85\n  safety: 1.0\n",
    )
    m = SolutionManifest.load(p)
    assert m.thresholds == {"functional": 0.85, "safety": 1.0}


def test_load_thresholds_defaults_to_empty(tmp_path: Path) -> None:
    p = _write_manifest(tmp_path, "solution: s\nagents:\n  - name: a1\n")
    m = SolutionManifest.load(p)
    assert m.thresholds == {}


def test_load_raises_when_solution_missing(tmp_path: Path) -> None:
    p = _write_manifest(tmp_path, "agents:\n  - name: a1\n")
    with pytest.raises(ValueError, match="missing required field 'solution'"):
        SolutionManifest.load(p)


def test_load_raises_when_agents_empty(tmp_path: Path) -> None:
    p = _write_manifest(tmp_path, "solution: s\nagents: []\n")
    with pytest.raises(ValueError, match="'agents' must be a non-empty list"):
        SolutionManifest.load(p)


def test_load_raises_when_agents_missing(tmp_path: Path) -> None:
    p = _write_manifest(tmp_path, "solution: s\n")
    with pytest.raises(ValueError, match="'agents' must be a non-empty list"):
        SolutionManifest.load(p)


# ── SolutionManifest.validate — agent file checks ────────────────────────────


def test_validate_passes_when_all_agents_exist(tmp_path: Path) -> None:
    cases = tmp_path / "cases"
    _scaffold_agent(cases, "scheduling-v1")
    _scaffold_agent(cases, "billing-v1")
    p = _write_manifest(
        tmp_path,
        "solution: s\nagents:\n  - name: scheduling-v1\n  - name: billing-v1\n",
    )
    m = SolutionManifest.load(p)
    m.validate(cases)  # should not raise


def test_validate_raises_for_missing_agent_yaml(tmp_path: Path) -> None:
    cases = tmp_path / "cases"
    cases.mkdir()
    p = _write_manifest(tmp_path, "solution: s\nagents:\n  - name: ghost-agent\n")
    m = SolutionManifest.load(p)
    with pytest.raises(CaseValidationError, match="ghost-agent.*agent.yaml not found"):
        m.validate(cases)


def test_validate_collects_multiple_missing_agents(tmp_path: Path) -> None:
    cases = tmp_path / "cases"
    cases.mkdir()
    p = _write_manifest(
        tmp_path,
        "solution: s\nagents:\n  - name: missing-a\n  - name: missing-b\n",
    )
    m = SolutionManifest.load(p)
    with pytest.raises(CaseValidationError) as exc_info:
        m.validate(cases)
    msg = str(exc_info.value)
    assert "missing-a" in msg
    assert "missing-b" in msg


# ── SolutionManifest.validate — stub fixture checks ──────────────────────────


def test_validate_passes_stub_agent_with_fixtures(tmp_path: Path) -> None:
    cases = tmp_path / "cases"
    stubs = tmp_path / "stubs"
    _scaffold_agent(cases, "referral-v1")
    _scaffold_stubs(stubs, "referral-v1")
    p = _write_manifest(
        tmp_path,
        "solution: s\nagents:\n  - name: referral-v1\n    stub: true\n",
    )
    m = SolutionManifest.load(p)
    m.validate(cases, stubs_path=stubs)  # should not raise


def test_validate_raises_for_stub_agent_without_fixtures(tmp_path: Path) -> None:
    cases = tmp_path / "cases"
    stubs = tmp_path / "stubs"
    _scaffold_agent(cases, "referral-v1")
    # no fixtures written under stubs/referral-v1/
    p = _write_manifest(
        tmp_path,
        "solution: s\nagents:\n  - name: referral-v1\n    stub: true\n",
    )
    m = SolutionManifest.load(p)
    with pytest.raises(CaseValidationError, match="stub=true but no fixture files"):
        m.validate(cases, stubs_path=stubs)


def test_validate_live_agent_skips_stub_check(tmp_path: Path) -> None:
    cases = tmp_path / "cases"
    stubs = tmp_path / "stubs"
    _scaffold_agent(cases, "scheduling-v1")
    # stubs dir doesn't exist at all — fine for stub: false agent
    p = _write_manifest(
        tmp_path,
        "solution: s\nagents:\n  - name: scheduling-v1\n    stub: false\n",
    )
    m = SolutionManifest.load(p)
    m.validate(cases, stubs_path=stubs)  # should not raise


# ── SolutionManifest.validate — threshold category checks ────────────────────


def test_validate_passes_known_threshold_categories(tmp_path: Path) -> None:
    cases = tmp_path / "cases"
    _scaffold_agent(cases, "scheduling-v1")
    p = _write_manifest(
        tmp_path,
        "solution: s\nagents:\n  - name: scheduling-v1\nthresholds:\n  functional: 0.85\n  safety: 1.0\n",
    )
    m = SolutionManifest.load(p)
    m.validate(cases)  # should not raise


def test_validate_raises_for_unknown_threshold_category(tmp_path: Path) -> None:
    cases = tmp_path / "cases"
    _scaffold_agent(cases, "scheduling-v1")
    p = _write_manifest(
        tmp_path,
        "solution: s\nagents:\n  - name: scheduling-v1\nthresholds:\n  bogus_category: 0.9\n",
    )
    m = SolutionManifest.load(p)
    with pytest.raises(CaseValidationError, match="bogus_category.*not a recognised category"):
        m.validate(cases)


# ── SolutionResult and delta_vs_baseline ─────────────────────────────────────


def test_solution_result_create_sets_passed() -> None:
    from hlsharness.results import CategorySummary, EvalResults, SolutionResult

    cat_pass = CategorySummary("functional", 5, 5, 1.0, 0.8, True)
    agent_r = EvalResults.create(agent="scheduling-v1", cases=[], categories=[cat_pass])
    sol = SolutionResult.create(
        solution="prior-auth-v1",
        agent_results=[agent_r],
        solution_categories=[cat_pass],
    )
    assert sol.passed is True
    assert sol.solution == "prior-auth-v1"
    assert len(sol.agent_results) == 1


def test_solution_result_passed_false_when_any_category_fails() -> None:
    from hlsharness.results import CategorySummary, EvalResults, SolutionResult

    cat_fail = CategorySummary("safety", 5, 3, 0.6, 0.9, False)
    agent_r = EvalResults.create(agent="a", cases=[], categories=[cat_fail])
    sol = SolutionResult.create("s", [agent_r], [cat_fail])
    assert sol.passed is False


def test_solution_result_to_dict_round_trip() -> None:
    from hlsharness.results import CategorySummary, EvalResults, SolutionResult

    cat = CategorySummary("functional", 1, 1, 1.0, 0.8, True)
    agent_r = EvalResults.create(agent="a", cases=[], categories=[cat])
    sol = SolutionResult.create("my-solution", [agent_r], [cat])
    d = sol.to_dict()
    assert d["solution"] == "my-solution"
    assert d["passed"] is True
    assert len(d["agent_results"]) == 1
    assert len(d["solution_categories"]) == 1


def test_case_result_delta_vs_baseline_defaults_none() -> None:
    from hlsharness.results import CaseResult

    cr = CaseResult(
        case_id="TC-001",
        agent="a",
        category="functional",
        input_summary="hi",
        score=1.0,
        passed=True,
        rationale="ok",
        trajectory=[],
        latency_ms=10.0,
        prompt_tokens=0,
        completion_tokens=0,
    )
    assert cr.delta_vs_baseline is None


def test_case_result_accepts_delta_vs_baseline() -> None:
    from hlsharness.results import CaseResult

    cr = CaseResult(
        case_id="TC-001",
        agent="a",
        category="functional",
        input_summary="hi",
        score=0.9,
        passed=True,
        rationale="ok",
        trajectory=[],
        latency_ms=10.0,
        prompt_tokens=0,
        completion_tokens=0,
        delta_vs_baseline=-0.1,
    )
    assert cr.delta_vs_baseline == pytest.approx(-0.1)


# ── AgentEntry.depends_on ─────────────────────────────────────────────────────


def test_load_parses_depends_on(tmp_path: Path) -> None:
    p = _write_manifest(
        tmp_path,
        (
            "solution: s\nagents:\n"
            "  - name: orchestrator\n"
            "  - name: booking-agent\n"
            "    depends_on:\n"
            "      - orchestrator\n"
        ),
    )
    m = SolutionManifest.load(p)
    assert m.agents[0].depends_on == []
    assert m.agents[1].depends_on == ["orchestrator"]


def test_load_depends_on_defaults_to_empty(tmp_path: Path) -> None:
    p = _write_manifest(tmp_path, "solution: s\nagents:\n  - name: a1\n")
    m = SolutionManifest.load(p)
    assert m.agents[0].depends_on == []


def test_agent_entry_equality_with_depends_on() -> None:
    a = AgentEntry(name="booking-agent", stub=False, depends_on=["orchestrator"])
    b = AgentEntry(name="booking-agent", stub=False, depends_on=["orchestrator"])
    assert a == b


def test_agent_entry_inequality_on_depends_on() -> None:
    a = AgentEntry(name="booking-agent", depends_on=["orchestrator"])
    b = AgentEntry(name="booking-agent", depends_on=[])
    assert a != b
