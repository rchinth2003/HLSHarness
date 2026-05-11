"""Unit tests for RunStore — SQLite persistence for EvalResults.

Tests cover the public contract: save/load round-trips, baseline flag
exclusivity, None returned when no baseline exists, and history ordering.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hlsharness.results import CategorySummary, EvalResults
from hlsharness.run_store import RunStore


def _make_result(
    agent: str = "scheduling-v1",
    passed: bool = True,
    pass_rate: float = 1.0,
) -> EvalResults:
    categories = [
        CategorySummary(
            category="functional",
            total=5,
            passed_count=5 if passed else 3,
            pass_rate=pass_rate,
            threshold=0.8,
            met_threshold=passed,
        )
    ]
    return EvalResults.create(agent=agent, cases=[], categories=categories)


@pytest.fixture
def store(tmp_path: Path) -> RunStore:
    return RunStore(db_path=tmp_path / "test.db")


# ── save / load round-trip ────────────────────────────────────────────────────


def test_save_returns_positive_run_id(store: RunStore) -> None:
    result = _make_result()
    run_id = store.save(result)
    assert run_id > 0


def test_save_persists_agent_and_categories(store: RunStore) -> None:
    result = _make_result(agent="billing-v1", pass_rate=0.9)
    run_id = store.save(result, version="1.0")
    records = store.history("billing-v1")
    assert len(records) == 1
    assert records[0].id == run_id
    assert records[0].agent == "billing-v1"
    assert records[0].version == "1.0"
    assert len(records[0].categories) == 1
    assert records[0].categories[0].pass_rate == pytest.approx(0.9)


def test_save_records_passed_flag(store: RunStore) -> None:
    store.save(_make_result(passed=True))
    store.save(_make_result(passed=False))
    records = store.history("scheduling-v1")
    assert any(r.passed for r in records)
    assert any(not r.passed for r in records)


def test_save_accepts_solution(store: RunStore) -> None:
    result = _make_result()
    store.save(result, solution="prior-auth-v1")
    records = store.history("scheduling-v1")
    assert records[0].solution == "prior-auth-v1"


# ── load_baseline ─────────────────────────────────────────────────────────────


def test_load_baseline_returns_none_when_no_baseline(store: RunStore) -> None:
    store.save(_make_result(), is_baseline=False)
    assert store.load_baseline("scheduling-v1") is None


def test_load_baseline_returns_promoted_run(store: RunStore) -> None:
    run_id = store.save(_make_result(), is_baseline=True)
    baseline = store.load_baseline("scheduling-v1")
    assert baseline is not None
    assert baseline.id == run_id
    assert baseline.is_baseline is True


def test_load_baseline_returns_none_for_different_agent(store: RunStore) -> None:
    store.save(_make_result(agent="billing-v1"), is_baseline=True)
    assert store.load_baseline("scheduling-v1") is None


def test_load_baseline_filters_by_version(store: RunStore) -> None:
    store.save(_make_result(), version="1.0", is_baseline=True)
    store.save(_make_result(), version="2.0", is_baseline=True)
    baseline_v1 = store.load_baseline("scheduling-v1", version="1.0")
    baseline_v2 = store.load_baseline("scheduling-v1", version="2.0")
    assert baseline_v1 is not None
    assert baseline_v2 is not None
    assert baseline_v1.id != baseline_v2.id


# ── promote_baseline — exclusivity ────────────────────────────────────────────


def test_promote_baseline_sets_flag(store: RunStore) -> None:
    run_id = store.save(_make_result())
    store.promote_baseline(run_id)
    baseline = store.load_baseline("scheduling-v1")
    assert baseline is not None
    assert baseline.id == run_id


def test_promote_baseline_clears_previous_baseline(store: RunStore) -> None:
    first_id = store.save(_make_result(), is_baseline=True)
    second_id = store.save(_make_result())
    store.promote_baseline(second_id)

    records = store.history("scheduling-v1")
    by_id = {r.id: r for r in records}
    assert by_id[first_id].is_baseline is False
    assert by_id[second_id].is_baseline is True


def test_promote_baseline_raises_for_unknown_id(store: RunStore) -> None:
    with pytest.raises(ValueError, match="no run with id=999"):
        store.promote_baseline(999)


def test_only_one_baseline_per_agent_version_after_multiple_promotes(store: RunStore) -> None:
    ids = [store.save(_make_result(), version="1.0") for _ in range(3)]
    for run_id in ids:
        store.promote_baseline(run_id)
    records = store.history("scheduling-v1")
    baselines = [r for r in records if r.is_baseline]
    assert len(baselines) == 1
    assert baselines[0].id == ids[-1]


# ── history ordering ──────────────────────────────────────────────────────────


def test_history_ordered_by_run_at_descending(store: RunStore) -> None:
    for _ in range(3):
        store.save(_make_result())
    records = store.history("scheduling-v1")
    assert len(records) == 3
    run_ats = [r.run_at for r in records]
    assert run_ats == sorted(run_ats, reverse=True)


def test_history_limit_respected(store: RunStore) -> None:
    for _ in range(5):
        store.save(_make_result())
    records = store.history("scheduling-v1", limit=2)
    assert len(records) == 2


def test_history_empty_for_unknown_agent(store: RunStore) -> None:
    store.save(_make_result(agent="billing-v1"))
    assert store.history("scheduling-v1") == []


# ── EvalController integration ────────────────────────────────────────────────


def test_eval_controller_saves_to_run_store(tmp_path: Path) -> None:
    """EvalController calls run_store.save() when run_store is provided."""
    saved: list[EvalResults] = []

    class _FakeStore:
        def save(self, result: EvalResults, **_: object) -> int:
            saved.append(result)
            return 1

    from unittest.mock import AsyncMock, MagicMock, patch

    from hlsharness.controller import EvalController

    fake_maf_response = MagicMock()
    fake_maf_response.text = "ok"
    fake_agent = MagicMock()
    fake_agent.run = AsyncMock(return_value=fake_maf_response)
    fake_agent_yaml = MagicMock()
    fake_agent_yaml.name = "scheduling-v1"
    fake_agent_yaml.tools = []
    fake_agent_yaml.x_harness = MagicMock(
        categories=["functional"], thresholds={"functional": 0.8}, personas=[]
    )

    class _FakeJudge:
        def score(self, category, case, response):
            from hlsharness.base_scorer import JudgeResult

            return JudgeResult(score=1.0, passed=True, rationale="ok")

    cases_path = tmp_path / "cases"
    (cases_path / "scheduling-v1" / "functional").mkdir(parents=True)
    case_yaml = cases_path / "scheduling-v1" / "functional" / "TC-001.yaml"
    case_yaml.write_text(
        "id: TC-001\nagent: scheduling-v1\ncategory: functional\n"
        "input:\n  messages:\n    - role: user\n      content: Book me\n"
        "tool_responses: {}\nexpected:\n  outcome: booked\n"
    )

    store = _FakeStore()
    with (
        patch("hlsharness.maf_agent.load_agent_yaml", return_value=fake_agent_yaml),
        patch("hlsharness.maf_agent.build_maf_agent", return_value=fake_agent),
        patch("hlsharness.stub_middleware.StubToolMiddleware"),
    ):
        ctrl = EvalController(
            agent_yaml_path=tmp_path / "agent.yaml",
            judge=_FakeJudge(),
            cases_path=cases_path,
            run_store=store,
        )
        ctrl.run()

    assert len(saved) == 1
    assert saved[0].agent == "scheduling-v1"
