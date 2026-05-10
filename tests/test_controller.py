"""Unit tests for EvalController — no Azure credentials required.

All Azure calls are avoided by injecting a FakeAdapter and FakeJudge.
"""

from pathlib import Path

import pytest

from hlsharness.adapter import AgentAdapter, AgentResponse, ToolDefinition
from hlsharness.controller import EvalController
from hlsharness.judge import JudgeResult
from hlsharness.loader import TestCase
from hlsharness.simulator import ToolSimulator


class _FakeAdapter(AgentAdapter):
    @property
    def name(self) -> str:
        return "scheduling-v1"

    @property
    def system_prompt(self) -> str:
        return "Fake system prompt"

    @property
    def tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(name="search_available_slots", description=""),
            ToolDefinition(name="book_appointment", description=""),
            ToolDefinition(name="cancel_appointment", description=""),
        ]

    def run(self, messages: list[dict], tool_simulator: ToolSimulator) -> AgentResponse:  # type: ignore[override]
        return AgentResponse(
            content="Your appointment is booked.",
            prompt_tokens=100,
            completion_tokens=30,
        )


class _FakeJudge:
    def __init__(self, score: float = 0.9) -> None:
        self._score = score

    def score(self, category: str, case: TestCase, response: AgentResponse) -> JudgeResult:
        return JudgeResult(
            score=self._score,
            passed=self._score >= 0.8,
            rationale=f"Fake {category} rationale",
        )


def _make_controller(
    cases_path: Path,
    score: float = 0.9,
    thresholds: dict[str, float] | None = None,
) -> EvalController:
    return EvalController(
        adapter=_FakeAdapter(),
        judge=_FakeJudge(score=score),
        cases_path=cases_path,
        thresholds=thresholds,
    )


def test_run_returns_results_for_real_cases():
    results = _make_controller(Path("cases")).run(categories=["functional"])
    assert len(results.cases) == 3
    assert results.cases[0].agent == "scheduling-v1"


def test_passed_when_all_cases_above_threshold():
    results = _make_controller(Path("cases"), score=0.9).run(categories=["functional"])
    assert results.passed is True


def test_failed_when_cases_below_threshold():
    results = _make_controller(Path("cases"), score=0.5).run(categories=["functional"])
    assert results.passed is False


def test_category_summary_counts():
    results = _make_controller(Path("cases")).run(categories=["functional"])
    summary = results.categories[0]
    assert summary.total == 3
    assert summary.passed_count == 3
    assert summary.pass_rate == 1.0


def test_case_result_has_trajectory():
    results = _make_controller(Path("cases")).run(categories=["functional"])
    assert isinstance(results.cases[0].trajectory, list)


def test_case_result_has_latency():
    results = _make_controller(Path("cases")).run(categories=["functional"])
    assert results.cases[0].latency_ms >= 0.0


def test_case_result_has_token_counts():
    results = _make_controller(Path("cases")).run(categories=["functional"])
    assert results.cases[0].prompt_tokens == 100
    assert results.cases[0].completion_tokens == 30


def test_no_cases_raises():
    with pytest.raises(ValueError, match="No cases found"):
        _make_controller(Path("cases")).run(categories=["nonexistent"])


def test_custom_threshold_applied():
    # score=0.5 → FakeJudge marks all cases failed → pass_rate=0.0
    # custom threshold=0.0 → 0.0 >= 0.0 is True → overall passed
    # proves custom threshold overrides the default (0.8 would yield False)
    results = _make_controller(Path("cases"), score=0.5, thresholds={"functional": 0.0}).run(
        categories=["functional"]
    )
    assert results.passed is True


def test_results_contain_metadata():
    results = _make_controller(Path("cases")).run(categories=["functional"])
    tc003 = next(r for r in results.cases if r.case_id == "TC-003")
    assert tc003.metadata.get("language") == "spanish"


# ── Manifest integration ──────────────────────────────────────────────────────


def _write_manifest(cases_path: Path, thresholds: dict[str, float]) -> None:
    """Write a scheduling-v1 manifest to cases_path/scheduling-v1/manifest.yaml."""
    import yaml

    manifest_data = {
        "agent": "scheduling-v1",
        "description": "Scheduling agent",
        "categories": ["functional"],
        "tools": [
            {"name": "search_available_slots", "description": "Search slots"},
            {"name": "book_appointment", "description": "Book"},
            {"name": "cancel_appointment", "description": "Cancel"},
        ],
        "thresholds": thresholds,
    }
    manifest_dir = cases_path / "scheduling-v1"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    with (manifest_dir / "manifest.yaml").open("w") as fh:
        yaml.dump(manifest_data, fh)


def test_manifest_thresholds_override_defaults(tmp_path: Path):
    """Controller with a manifest uses manifest thresholds instead of DEFAULT_THRESHOLDS."""
    import shutil

    shutil.copytree("cases/scheduling", tmp_path / "scheduling")
    _write_manifest(tmp_path, thresholds={"functional": 0.42})

    controller = EvalController(
        adapter=_FakeAdapter(),
        judge=_FakeJudge(score=0.9),
        cases_path=tmp_path,
    )
    results = controller.run(categories=["functional"])
    functional_summary = next(s for s in results.categories if s.category == "functional")
    assert functional_summary.threshold == 0.42


def test_no_manifest_falls_back_to_default_thresholds():
    """Controller without a manifest uses DEFAULT_THRESHOLDS."""
    from hlsharness.controller import DEFAULT_THRESHOLDS

    results = _make_controller(Path("cases")).run(categories=["functional"])
    functional_summary = next(s for s in results.categories if s.category == "functional")
    assert functional_summary.threshold == DEFAULT_THRESHOLDS["functional"]


def test_manifest_validate_cases_uses_manifest_tools(tmp_path: Path):
    """_validate_cases uses manifest tool names when a manifest is present."""
    import shutil

    shutil.copytree("cases/scheduling", tmp_path / "scheduling")
    _write_manifest(tmp_path, thresholds={"functional": 0.8})

    controller = EvalController(
        adapter=_FakeAdapter(),
        judge=_FakeJudge(score=0.9),
        cases_path=tmp_path,
    )
    results = controller.run(categories=["functional"])
    assert len(results.cases) == 3


def test_explicit_thresholds_override_manifest(tmp_path: Path):
    """Explicit thresholds passed to EvalController override manifest thresholds."""
    import shutil

    shutil.copytree("cases/scheduling", tmp_path / "scheduling")
    _write_manifest(tmp_path, thresholds={"functional": 0.42})

    controller = EvalController(
        adapter=_FakeAdapter(),
        judge=_FakeJudge(score=0.9),
        cases_path=tmp_path,
        thresholds={"functional": 0.99},
    )
    results = controller.run(categories=["functional"])
    functional_summary = next(s for s in results.categories if s.category == "functional")
    assert functional_summary.threshold == 0.99
