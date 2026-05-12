"""E2E wiring tests for PatSch solution — SolutionController with real config/solution.yaml.

No Azure calls: EvalController patched to return scripted EvalResults per agent.
Covers: happy-path rollup, DAG gate exclusion when orchestrator fails, RunStore save,
triage empty-categories handling, and case_dir path resolution.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from hlsharness.results import CategorySummary, EvalResults, SolutionResult
from hlsharness.solution_controller import SolutionController
from hlsharness.solution_manifest import SolutionManifest

_MANIFEST_PATH = Path(__file__).parent.parent / "config" / "solution.yaml"


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_eval_results(
    agent: str,
    categories: list[tuple[str, float, float]],
) -> EvalResults:
    """Build an EvalResults with given (category, pass_rate, threshold) tuples."""
    cat_summaries = [
        CategorySummary(
            category=cat,
            total=10,
            passed_count=int(10 * rate),
            pass_rate=rate,
            threshold=thresh,
            met_threshold=rate >= thresh,
        )
        for cat, rate, thresh in categories
    ]
    return EvalResults(
        agent=agent,
        run_at="2026-05-12T00:00:00+00:00",
        cases=[],
        categories=cat_summaries,
        passed=all(c.met_threshold for c in cat_summaries),
    )


def _fake_ctrl_seq(seq: list[EvalResults]) -> type:
    """Return a fake EvalController class that pops results from seq in order."""
    idx = {"i": 0}

    class _FakeCtrl:
        def __init__(self, **_: object) -> None:
            pass

        def run(self, **_: object) -> EvalResults:
            r = seq[idx["i"]]
            idx["i"] += 1
            return r

    return _FakeCtrl


def _patsch_results(
    orch_functional: float = 1.0,
    orch_hitl: float = 1.0,
    sched_functional: float = 1.0,
    elig_functional: float = 1.0,
    elig_regulatory: float = 1.0,
    elig_hitl: float = 1.0,
    triage_urgency: float = 1.0,
    triage_safety: float = 1.0,
    triage_hitl: float = 1.0,
) -> list[EvalResults]:
    """Scripted L1 results for all 4 PatSch agents in manifest order."""
    return [
        _make_eval_results(
            "orchestrator",
            [("functional", orch_functional, 0.8), ("hitl_routing", orch_hitl, 0.9)],
        ),
        _make_eval_results(
            "scheduling-agent",
            [("functional", sched_functional, 0.8), ("equity", 1.0, 0.9)],
        ),
        _make_eval_results(
            "eligibility-agent",
            [
                ("functional", elig_functional, 0.8),
                ("privacy", 1.0, 1.0),
                ("regulatory_compliance", elig_regulatory, 0.95),
                ("hitl_routing", elig_hitl, 0.9),
            ],
        ),
        _make_eval_results(
            "triage-agent",
            [
                ("urgency_triage", triage_urgency, 0.9),
                ("safety", triage_safety, 0.9),
                ("hitl_routing", triage_hitl, 0.9),
            ],
        ),
    ]


# ── happy path ────────────────────────────────────────────────────────────────


def test_patsch_happy_path_solution_passes(tmp_path: Path) -> None:
    manifest = SolutionManifest.load(_MANIFEST_PATH)
    ctrl = SolutionController(manifest=manifest, judge=MagicMock(), cases_path=tmp_path)
    with patch("hlsharness.solution_controller.EvalController", _fake_ctrl_seq(_patsch_results())):
        result = ctrl.run()
    assert result.passed is True


def test_patsch_happy_path_solution_name(tmp_path: Path) -> None:
    manifest = SolutionManifest.load(_MANIFEST_PATH)
    ctrl = SolutionController(manifest=manifest, judge=MagicMock(), cases_path=tmp_path)
    with patch("hlsharness.solution_controller.EvalController", _fake_ctrl_seq(_patsch_results())):
        result = ctrl.run()
    assert result.solution == "patient-scheduling-v1"


def test_patsch_happy_path_four_agent_results(tmp_path: Path) -> None:
    manifest = SolutionManifest.load(_MANIFEST_PATH)
    ctrl = SolutionController(manifest=manifest, judge=MagicMock(), cases_path=tmp_path)
    with patch("hlsharness.solution_controller.EvalController", _fake_ctrl_seq(_patsch_results())):
        result = ctrl.run()
    agent_names = {r.agent for r in result.agent_results}
    assert agent_names == {"orchestrator", "scheduling-agent", "eligibility-agent", "triage-agent"}


def test_patsch_happy_path_expected_categories_in_rollup(tmp_path: Path) -> None:
    manifest = SolutionManifest.load(_MANIFEST_PATH)
    ctrl = SolutionController(manifest=manifest, judge=MagicMock(), cases_path=tmp_path)
    with patch("hlsharness.solution_controller.EvalController", _fake_ctrl_seq(_patsch_results())):
        result = ctrl.run()
    cats = {c.category for c in result.solution_categories}
    assert cats == {
        "functional",
        "hitl_routing",
        "equity",
        "privacy",
        "urgency_triage",
        "safety",
        "regulatory_compliance",
    }


def test_patsch_functional_rollup_aggregates_three_active_agents(tmp_path: Path) -> None:
    manifest = SolutionManifest.load(_MANIFEST_PATH)
    ctrl = SolutionController(manifest=manifest, judge=MagicMock(), cases_path=tmp_path)
    with patch("hlsharness.solution_controller.EvalController", _fake_ctrl_seq(_patsch_results())):
        result = ctrl.run()
    # functional: orchestrator (10) + scheduling (10) + eligibility (10) = 30 total
    func = next(c for c in result.solution_categories if c.category == "functional")
    assert func.total == 30


# ── RunStore integration ──────────────────────────────────────────────────────


def test_patsch_run_store_save_called_on_passing_run(tmp_path: Path) -> None:
    manifest = SolutionManifest.load(_MANIFEST_PATH)
    saved: list[SolutionResult] = []

    class _FakeStore:
        def save(self, result: SolutionResult, **_: object) -> int:
            saved.append(result)
            return 1

    ctrl = SolutionController(
        manifest=manifest,
        judge=MagicMock(),
        cases_path=tmp_path,
        run_store=_FakeStore(),
    )
    with patch("hlsharness.solution_controller.EvalController", _fake_ctrl_seq(_patsch_results())):
        ctrl.run()

    assert len(saved) == 1
    assert saved[0].solution == "patient-scheduling-v1"
    assert saved[0].passed is True


# ── DAG gate — orchestrator hitl_routing fails ────────────────────────────────


def test_patsch_dag_equity_excluded_when_orchestrator_hitl_routing_fails(
    tmp_path: Path,
) -> None:
    manifest = SolutionManifest.load(_MANIFEST_PATH)
    ctrl = SolutionController(manifest=manifest, judge=MagicMock(), cases_path=tmp_path)
    # orch_hitl=0.5 → met_threshold=False (0.5 < 0.9) → scheduling-agent excluded
    with patch(
        "hlsharness.solution_controller.EvalController",
        _fake_ctrl_seq(_patsch_results(orch_hitl=0.5)),
    ):
        result = ctrl.run()
    cats = {c.category for c in result.solution_categories}
    assert "equity" not in cats  # equity only comes from scheduling-agent


def test_patsch_dag_privacy_excluded_when_orchestrator_hitl_routing_fails(
    tmp_path: Path,
) -> None:
    manifest = SolutionManifest.load(_MANIFEST_PATH)
    ctrl = SolutionController(manifest=manifest, judge=MagicMock(), cases_path=tmp_path)
    with patch(
        "hlsharness.solution_controller.EvalController",
        _fake_ctrl_seq(_patsch_results(orch_hitl=0.5)),
    ):
        result = ctrl.run()
    cats = {c.category for c in result.solution_categories}
    assert "privacy" not in cats  # privacy only comes from eligibility-agent


def test_patsch_dag_orchestrator_in_rollup_when_hitl_routing_fails(tmp_path: Path) -> None:
    manifest = SolutionManifest.load(_MANIFEST_PATH)
    ctrl = SolutionController(manifest=manifest, judge=MagicMock(), cases_path=tmp_path)
    with patch(
        "hlsharness.solution_controller.EvalController",
        _fake_ctrl_seq(_patsch_results(orch_hitl=0.5)),
    ):
        result = ctrl.run()
    # orchestrator has no deps → always included regardless of its own category failures
    cats = {c.category for c in result.solution_categories}
    assert "functional" in cats
    assert "hitl_routing" in cats


# ── DAG gate — orchestrator functional fails ──────────────────────────────────


def test_patsch_dag_sub_agents_excluded_when_orchestrator_functional_fails(
    tmp_path: Path,
) -> None:
    manifest = SolutionManifest.load(_MANIFEST_PATH)
    ctrl = SolutionController(manifest=manifest, judge=MagicMock(), cases_path=tmp_path)
    # orch_functional=0.5 → met_threshold=False (0.5 < 0.8) → all sub-agents excluded
    with patch(
        "hlsharness.solution_controller.EvalController",
        _fake_ctrl_seq(_patsch_results(orch_functional=0.5)),
    ):
        result = ctrl.run()
    cats = {c.category for c in result.solution_categories}
    assert "equity" not in cats
    assert "privacy" not in cats


def test_patsch_dag_triage_excluded_when_orchestrator_hitl_routing_fails(
    tmp_path: Path,
) -> None:
    manifest = SolutionManifest.load(_MANIFEST_PATH)
    ctrl = SolutionController(manifest=manifest, judge=MagicMock(), cases_path=tmp_path)
    with patch(
        "hlsharness.solution_controller.EvalController",
        _fake_ctrl_seq(_patsch_results(orch_hitl=0.5)),
    ):
        result = ctrl.run()
    cats = {c.category for c in result.solution_categories}
    # urgency_triage and safety only come from triage-agent, which depends_on orchestrator
    assert "urgency_triage" not in cats
    assert "safety" not in cats


def test_patsch_dag_triage_excluded_when_orchestrator_functional_fails(
    tmp_path: Path,
) -> None:
    manifest = SolutionManifest.load(_MANIFEST_PATH)
    ctrl = SolutionController(manifest=manifest, judge=MagicMock(), cases_path=tmp_path)
    with patch(
        "hlsharness.solution_controller.EvalController",
        _fake_ctrl_seq(_patsch_results(orch_functional=0.5)),
    ):
        result = ctrl.run()
    cats = {c.category for c in result.solution_categories}
    assert "urgency_triage" not in cats
    assert "safety" not in cats


# ── case_dir path resolution ──────────────────────────────────────────────────


def test_patsch_eval_controller_uses_correct_case_dir_paths(tmp_path: Path) -> None:
    manifest = SolutionManifest.load(_MANIFEST_PATH)
    captured: list[Path] = []

    class _CapturingCtrl:
        def __init__(self, agent_yaml_path: Path, **_: object) -> None:
            captured.append(agent_yaml_path)

        def run(self, **_: object) -> EvalResults:
            return EvalResults(
                agent="x", run_at="2026-05-12T00:00:00+00:00", cases=[], categories=[], passed=True
            )

    ctrl = SolutionController(manifest=manifest, judge=MagicMock(), cases_path=tmp_path)
    with patch("hlsharness.solution_controller.EvalController", _CapturingCtrl):
        ctrl.run()

    dir_names = {p.parent.name for p in captured}
    assert "orchestrator-v1" in dir_names
    assert "scheduling-v1" in dir_names
    assert "eligibility-v1" in dir_names
    assert "triage-v1" in dir_names
