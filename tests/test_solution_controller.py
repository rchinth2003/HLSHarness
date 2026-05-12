"""Unit tests for SolutionController — L2 multi-agent solution eval.

Tests cover the public contract: correct L1 delegation per agent, L2 rollup
math, solution-level threshold application, and stub=true agent handling.
No Azure calls are made — EvalController is patched to return fake EvalResults.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hlsharness.results import CategorySummary, EvalResults, SolutionResult
from hlsharness.solution_controller import SolutionController
from hlsharness.solution_manifest import AgentEntry, SolutionManifest

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_manifest(
    agents: list[str],
    thresholds: dict[str, float] | None = None,
    stubs: dict[str, bool] | None = None,
) -> SolutionManifest:
    entries = [AgentEntry(name=a, stub=(stubs or {}).get(a, False)) for a in agents]
    return SolutionManifest(
        solution="test-solution",
        agents=entries,
        thresholds=thresholds or {},
    )


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
        run_at="2026-05-11T00:00:00+00:00",
        cases=[],
        categories=cat_summaries,
        passed=all(c.met_threshold for c in cat_summaries),
    )


def _make_controller(
    manifest: SolutionManifest,
    agent_results_seq: list[EvalResults],
    cases_path: Path | None = None,
) -> SolutionController:
    """Build a SolutionController with a fake Judge; EvalController is patched."""
    return SolutionController(
        manifest=manifest,
        judge=MagicMock(),
        cases_path=cases_path or Path("cases"),
    )


# ── basic L1 delegation ───────────────────────────────────────────────────────


def test_run_invokes_eval_controller_once_per_agent(tmp_path: Path) -> None:
    manifest = _make_manifest(["agent-a", "agent-b"])
    results_a = _make_eval_results("agent-a", [("functional", 1.0, 0.8)])
    results_b = _make_eval_results("agent-b", [("functional", 0.9, 0.8)])

    call_order: list[str] = []

    class _FakeCtrl:
        def __init__(self, agent_yaml_path: Path, **_: object) -> None:
            self._name = agent_yaml_path.parent.name

        def run(self, **_: object) -> EvalResults:
            call_order.append(self._name)
            return results_a if self._name == "agent-a" else results_b

    ctrl = _make_controller(manifest, [], cases_path=tmp_path)
    with patch("hlsharness.solution_controller.EvalController", _FakeCtrl):
        result = ctrl.run()

    assert call_order == ["agent-a", "agent-b"]
    assert len(result.agent_results) == 2


def test_run_returns_solution_result(tmp_path: Path) -> None:
    manifest = _make_manifest(["agent-a"])
    fake_results = _make_eval_results("agent-a", [("functional", 1.0, 0.8)])

    class _FakeCtrl:
        def __init__(self, **_: object) -> None:
            pass

        def run(self, **_: object) -> EvalResults:
            return fake_results

    ctrl = _make_controller(manifest, [], cases_path=tmp_path)
    with patch("hlsharness.solution_controller.EvalController", _FakeCtrl):
        result = ctrl.run()

    assert isinstance(result, SolutionResult)
    assert result.solution == "test-solution"


def test_agent_results_preserve_l1_data(tmp_path: Path) -> None:
    manifest = _make_manifest(["scheduling-v1"])
    l1 = _make_eval_results("scheduling-v1", [("safety", 0.9, 0.9)])

    class _FakeCtrl:
        def __init__(self, **_: object) -> None:
            pass

        def run(self, **_: object) -> EvalResults:
            return l1

    ctrl = _make_controller(manifest, [], cases_path=tmp_path)
    with patch("hlsharness.solution_controller.EvalController", _FakeCtrl):
        result = ctrl.run()

    assert result.agent_results[0].agent == "scheduling-v1"
    assert result.agent_results[0].categories[0].pass_rate == pytest.approx(0.9)


# ── L2 rollup math ────────────────────────────────────────────────────────────


def test_rollup_single_agent_single_category(tmp_path: Path) -> None:
    manifest = _make_manifest(["agent-a"])
    l1 = _make_eval_results("agent-a", [("functional", 0.8, 0.8)])

    class _FakeCtrl:
        def __init__(self, **_: object) -> None:
            pass

        def run(self, **_: object) -> EvalResults:
            return l1

    ctrl = _make_controller(manifest, [], cases_path=tmp_path)
    with patch("hlsharness.solution_controller.EvalController", _FakeCtrl):
        result = ctrl.run()

    assert len(result.solution_categories) == 1
    assert result.solution_categories[0].category == "functional"
    assert result.solution_categories[0].pass_rate == pytest.approx(0.8)


def test_rollup_averages_across_agents_weighted_by_case_count(tmp_path: Path) -> None:
    """10 cases at 80% + 10 cases at 100% → 18/20 = 90%."""
    manifest = _make_manifest(["agent-a", "agent-b"])

    def _fake_ctrl_factory(seq: list[EvalResults]) -> type:
        idx = {"i": 0}

        class _FakeCtrl:
            def __init__(self, **_: object) -> None:
                pass

            def run(self, **_: object) -> EvalResults:
                r = seq[idx["i"]]
                idx["i"] += 1
                return r

        return _FakeCtrl

    results_a = _make_eval_results("agent-a", [("functional", 0.8, 0.8)])
    results_b = _make_eval_results("agent-b", [("functional", 1.0, 0.8)])

    ctrl = _make_controller(manifest, [], cases_path=tmp_path)
    FakeCtrl = _fake_ctrl_factory([results_a, results_b])
    with patch("hlsharness.solution_controller.EvalController", FakeCtrl):
        result = ctrl.run()

    cat = next(c for c in result.solution_categories if c.category == "functional")
    assert cat.total == 20
    assert cat.passed_count == 18
    assert cat.pass_rate == pytest.approx(0.9)


def test_rollup_multiple_categories(tmp_path: Path) -> None:
    manifest = _make_manifest(["agent-a"])
    l1 = _make_eval_results("agent-a", [("functional", 1.0, 0.8), ("safety", 0.9, 0.9)])

    class _FakeCtrl:
        def __init__(self, **_: object) -> None:
            pass

        def run(self, **_: object) -> EvalResults:
            return l1

    ctrl = _make_controller(manifest, [], cases_path=tmp_path)
    with patch("hlsharness.solution_controller.EvalController", _FakeCtrl):
        result = ctrl.run()

    cats = {c.category for c in result.solution_categories}
    assert cats == {"functional", "safety"}


def test_rollup_categories_sorted_alphabetically(tmp_path: Path) -> None:
    manifest = _make_manifest(["agent-a"])
    l1 = _make_eval_results(
        "agent-a",
        [("safety", 0.9, 0.9), ("functional", 1.0, 0.8), ("equity", 0.95, 0.9)],
    )

    class _FakeCtrl:
        def __init__(self, **_: object) -> None:
            pass

        def run(self, **_: object) -> EvalResults:
            return l1

    ctrl = _make_controller(manifest, [], cases_path=tmp_path)
    with patch("hlsharness.solution_controller.EvalController", _FakeCtrl):
        result = ctrl.run()

    names = [c.category for c in result.solution_categories]
    assert names == sorted(names)


# ── threshold application ─────────────────────────────────────────────────────


def test_manifest_threshold_overrides_default(tmp_path: Path) -> None:
    manifest = _make_manifest(["agent-a"], thresholds={"functional": 0.95})
    l1 = _make_eval_results("agent-a", [("functional", 0.9, 0.8)])

    class _FakeCtrl:
        def __init__(self, **_: object) -> None:
            pass

        def run(self, **_: object) -> EvalResults:
            return l1

    ctrl = _make_controller(manifest, [], cases_path=tmp_path)
    with patch("hlsharness.solution_controller.EvalController", _FakeCtrl):
        result = ctrl.run()

    cat = result.solution_categories[0]
    assert cat.threshold == pytest.approx(0.95)
    assert cat.met_threshold is False  # 0.9 < 0.95


def test_passed_true_when_all_categories_meet_threshold(tmp_path: Path) -> None:
    manifest = _make_manifest(["agent-a"], thresholds={"functional": 0.8})
    l1 = _make_eval_results("agent-a", [("functional", 1.0, 0.8)])

    class _FakeCtrl:
        def __init__(self, **_: object) -> None:
            pass

        def run(self, **_: object) -> EvalResults:
            return l1

    ctrl = _make_controller(manifest, [], cases_path=tmp_path)
    with patch("hlsharness.solution_controller.EvalController", _FakeCtrl):
        result = ctrl.run()

    assert result.passed is True


def test_passed_false_when_any_category_fails(tmp_path: Path) -> None:
    manifest = _make_manifest(["agent-a"])
    l1 = _make_eval_results("agent-a", [("safety", 0.5, 0.9)])

    class _FakeCtrl:
        def __init__(self, **_: object) -> None:
            pass

        def run(self, **_: object) -> EvalResults:
            return l1

    ctrl = _make_controller(manifest, [], cases_path=tmp_path)
    with patch("hlsharness.solution_controller.EvalController", _FakeCtrl):
        result = ctrl.run()

    assert result.passed is False


# ── stub=true agents ──────────────────────────────────────────────────────────


def test_stub_agent_still_runs_eval_controller(tmp_path: Path) -> None:
    manifest = _make_manifest(["agent-a"], stubs={"agent-a": True})
    l1 = _make_eval_results("agent-a", [("functional", 1.0, 0.8)])
    ran: list[bool] = []

    class _FakeCtrl:
        def __init__(self, **_: object) -> None:
            pass

        def run(self, **_: object) -> EvalResults:
            ran.append(True)
            return l1

    ctrl = _make_controller(manifest, [], cases_path=tmp_path)
    with patch("hlsharness.solution_controller.EvalController", _FakeCtrl):
        ctrl.run()

    assert ran == [True]


# ── run_store integration ─────────────────────────────────────────────────────


def test_run_store_save_called_with_solution_result(tmp_path: Path) -> None:
    manifest = _make_manifest(["agent-a"])
    l1 = _make_eval_results("agent-a", [("functional", 1.0, 0.8)])
    saved: list[SolutionResult] = []

    class _FakeStore:
        def save(self, result: SolutionResult, **_: object) -> int:
            saved.append(result)
            return 1

    class _FakeCtrl:
        def __init__(self, **_: object) -> None:
            pass

        def run(self, **_: object) -> EvalResults:
            return l1

    ctrl = SolutionController(
        manifest=manifest,
        judge=MagicMock(),
        cases_path=tmp_path,
        run_store=_FakeStore(),
    )
    with patch("hlsharness.solution_controller.EvalController", _FakeCtrl):
        ctrl.run()

    assert len(saved) == 1
    assert saved[0].solution == "test-solution"


# ── CLI --solution flag ───────────────────────────────────────────────────────


def test_solution_flag_default_none() -> None:
    from hlsharness.__main__ import _build_parser

    args = _build_parser().parse_args([])
    assert args.solution is None


def test_solution_flag_sets_name() -> None:
    from hlsharness.__main__ import _build_parser

    args = _build_parser().parse_args(["--solution", "prior-auth-v1"])
    assert args.solution == "prior-auth-v1"


# ── DAG routing-gate tests ────────────────────────────────────────────────────


def _make_manifest_with_deps(
    agents: list[tuple[str, list[str]]],
    thresholds: dict[str, float] | None = None,
) -> SolutionManifest:
    """Build a manifest where each tuple is (agent_name, depends_on)."""
    entries = [AgentEntry(name=name, depends_on=deps) for name, deps in agents]
    return SolutionManifest(solution="dag-test", agents=entries, thresholds=thresholds or {})


def _fake_ctrl_seq(seq: list[EvalResults]) -> type:
    idx = {"i": 0}

    class _FakeCtrl:
        def __init__(self, **_: object) -> None:
            pass

        def run(self, **_: object) -> EvalResults:
            r = seq[idx["i"]]
            idx["i"] += 1
            return r

    return _FakeCtrl


def test_dag_dep_agent_included_when_orchestrator_passes(tmp_path: Path) -> None:
    manifest = _make_manifest_with_deps([("orchestrator", []), ("booking-agent", ["orchestrator"])])
    orch = _make_eval_results(
        "orchestrator", [("functional", 1.0, 0.8), ("hitl_routing", 1.0, 0.9)]
    )
    booking = _make_eval_results("booking-agent", [("functional", 0.9, 0.8)])

    ctrl = _make_controller(manifest, [], cases_path=tmp_path)
    with patch("hlsharness.solution_controller.EvalController", _fake_ctrl_seq([orch, booking])):
        result = ctrl.run()

    # Both agents' functional cases should be aggregated: 10+10=20, 10+9=19
    cat = next(c for c in result.solution_categories if c.category == "functional")
    assert cat.total == 20
    assert cat.passed_count == 19


def test_dag_dep_agent_excluded_when_orchestrator_functional_fails(tmp_path: Path) -> None:
    manifest = _make_manifest_with_deps([("orchestrator", []), ("booking-agent", ["orchestrator"])])
    orch = _make_eval_results("orchestrator", [("functional", 0.4, 0.8)])  # fails (0.4 < 0.8)
    booking = _make_eval_results("booking-agent", [("functional", 1.0, 0.8)])

    ctrl = _make_controller(manifest, [], cases_path=tmp_path)
    with patch("hlsharness.solution_controller.EvalController", _fake_ctrl_seq([orch, booking])):
        result = ctrl.run()

    # Only orchestrator's functional cases counted; booking-agent excluded
    cat = next(c for c in result.solution_categories if c.category == "functional")
    assert cat.total == 10  # only orchestrator
    assert cat.passed_count == 4


def test_dag_dep_agent_excluded_when_hitl_routing_fails(tmp_path: Path) -> None:
    manifest = _make_manifest_with_deps([("orchestrator", []), ("booking-agent", ["orchestrator"])])
    orch = _make_eval_results(
        "orchestrator",
        [("functional", 1.0, 0.8), ("hitl_routing", 0.5, 0.9)],  # hitl fails
    )
    booking = _make_eval_results("booking-agent", [("functional", 1.0, 0.8)])

    ctrl = _make_controller(manifest, [], cases_path=tmp_path)
    with patch("hlsharness.solution_controller.EvalController", _fake_ctrl_seq([orch, booking])):
        result = ctrl.run()

    # booking-agent excluded because orchestrator hitl_routing failed
    cat = next(c for c in result.solution_categories if c.category == "functional")
    assert cat.total == 10  # only orchestrator's functional
    assert cat.passed_count == 10


def test_dag_no_deps_always_included(tmp_path: Path) -> None:
    manifest = _make_manifest_with_deps([("agent-a", []), ("agent-b", [])])
    r_a = _make_eval_results("agent-a", [("functional", 0.8, 0.8)])
    r_b = _make_eval_results("agent-b", [("functional", 0.9, 0.8)])

    ctrl = _make_controller(manifest, [], cases_path=tmp_path)
    with patch("hlsharness.solution_controller.EvalController", _fake_ctrl_seq([r_a, r_b])):
        result = ctrl.run()

    cat = next(c for c in result.solution_categories if c.category == "functional")
    assert cat.total == 20  # both included


def test_dag_missing_dep_in_results_excludes_agent(tmp_path: Path) -> None:
    """If a declared dep agent has no L1 result, dependent agent is excluded."""
    # Only one agent declared in manifest but it depends on "ghost" which isn't in manifest
    manifest = _make_manifest_with_deps([("booking-agent", ["ghost-agent"])])
    booking = _make_eval_results("booking-agent", [("functional", 1.0, 0.8)])

    ctrl = _make_controller(manifest, [], cases_path=tmp_path)
    with patch("hlsharness.solution_controller.EvalController", _fake_ctrl_seq([booking])):
        result = ctrl.run()

    assert result.solution_categories == []  # booking excluded; no categories to rollup
