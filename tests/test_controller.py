"""Unit tests for EvalController — no Azure credentials required.

All Azure calls are avoided by injecting a fake MAF agent and FakeJudge.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from hlsharness.controller import DEFAULT_THRESHOLDS, CaseValidationError, EvalController
from hlsharness.judge import JudgeResult
from hlsharness.loader import TestCase
from hlsharness.results import AgentResponse


class _FakeJudge:
    def __init__(self, score: float = 0.9) -> None:
        self._score = score

    def score(self, category: str, case: TestCase, response: AgentResponse) -> JudgeResult:
        return JudgeResult(
            score=self._score,
            passed=self._score >= 0.8,
            rationale=f"Fake {category} rationale",
        )


def _agent_yaml_path() -> Path:
    return Path("cases/scheduling-v1/agent.yaml")


def _make_fake_maf_agent(content: str = "Appointment booked.") -> object:
    fake_response = MagicMock()
    fake_response.text = content

    fake_agent = MagicMock()
    fake_agent.run = AsyncMock(return_value=fake_response)
    return fake_agent


def _make_controller(
    cases_path: Path,
    score: float = 0.9,
    thresholds: dict[str, float] | None = None,
    mock_agent: object | None = None,
    stubs_path: Path = Path("stubs"),
) -> EvalController:
    if mock_agent is None:
        mock_agent = _make_fake_maf_agent()
    with patch("hlsharness.maf_agent.build_maf_agent", return_value=mock_agent):
        return EvalController(
            agent_yaml_path=_agent_yaml_path(),
            judge=_FakeJudge(score=score),
            cases_path=cases_path,
            thresholds=thresholds,
            stubs_path=stubs_path,
        )


# -- Core eval flow ------------------------------------------------------------


def test_run_returns_results_for_real_cases(tmp_path: Path):
    shutil.copytree("cases/scheduling", tmp_path / "scheduling")
    results = _make_controller(tmp_path).run(categories=["functional"])
    assert len(results.cases) == 3
    assert results.cases[0].agent == "scheduling-v1"


def test_passed_when_all_cases_above_threshold(tmp_path: Path):
    shutil.copytree("cases/scheduling", tmp_path / "scheduling")
    results = _make_controller(tmp_path, score=0.9).run(categories=["functional"])
    assert results.passed is True


def test_failed_when_cases_below_threshold(tmp_path: Path):
    shutil.copytree("cases/scheduling", tmp_path / "scheduling")
    results = _make_controller(tmp_path, score=0.5).run(categories=["functional"])
    assert results.passed is False


def test_category_summary_counts(tmp_path: Path):
    shutil.copytree("cases/scheduling", tmp_path / "scheduling")
    results = _make_controller(tmp_path).run(categories=["functional"])
    summary = results.categories[0]
    assert summary.total == 3
    assert summary.passed_count == 3
    assert summary.pass_rate == 1.0


def test_case_result_has_trajectory(tmp_path: Path):
    shutil.copytree("cases/scheduling", tmp_path / "scheduling")
    results = _make_controller(tmp_path).run(categories=["functional"])
    assert isinstance(results.cases[0].trajectory, list)


def test_case_result_has_latency(tmp_path: Path):
    shutil.copytree("cases/scheduling", tmp_path / "scheduling")
    results = _make_controller(tmp_path).run(categories=["functional"])
    assert results.cases[0].latency_ms >= 0.0


def test_no_cases_raises(tmp_path: Path):
    shutil.copytree("cases/scheduling", tmp_path / "scheduling")
    with pytest.raises(ValueError, match="No cases found"):
        _make_controller(tmp_path).run(categories=["nonexistent"])


def test_custom_threshold_applied(tmp_path: Path):
    shutil.copytree("cases/scheduling", tmp_path / "scheduling")
    results = _make_controller(tmp_path, score=0.5, thresholds={"functional": 0.0}).run(
        categories=["functional"]
    )
    assert results.passed is True


def test_results_contain_metadata(tmp_path: Path):
    shutil.copytree("cases/scheduling", tmp_path / "scheduling")
    results = _make_controller(tmp_path).run(categories=["functional"])
    tc003 = next(r for r in results.cases if r.case_id == "TC-003")
    assert tc003.metadata.get("language") == "spanish"


# -- Threshold priority --------------------------------------------------------


def test_x_harness_thresholds_override_defaults(tmp_path: Path):
    shutil.copytree("cases/scheduling", tmp_path / "scheduling")
    results = _make_controller(tmp_path, score=0.9).run(categories=["functional"])
    functional_summary = next(s for s in results.categories if s.category == "functional")
    assert functional_summary.threshold == pytest.approx(0.8)


def test_explicit_thresholds_override_yaml(tmp_path: Path):
    shutil.copytree("cases/scheduling", tmp_path / "scheduling")
    results = _make_controller(tmp_path, score=0.9, thresholds={"functional": 0.42}).run(
        categories=["functional"]
    )
    functional_summary = next(s for s in results.categories if s.category == "functional")
    assert functional_summary.threshold == pytest.approx(0.42)


def test_no_explicit_thresholds_falls_back_to_yaml_then_defaults(tmp_path: Path):
    shutil.copytree("cases/scheduling", tmp_path / "scheduling")
    results = _make_controller(tmp_path, score=0.9).run(categories=["functional"])
    functional_summary = next(s for s in results.categories if s.category == "functional")
    assert functional_summary.threshold == pytest.approx(DEFAULT_THRESHOLDS["functional"])


# -- agent.yaml integration ----------------------------------------------------


def test_yaml_loads_agent_name():
    with patch("hlsharness.maf_agent.build_maf_agent", return_value=_make_fake_maf_agent()):
        controller = EvalController(
            agent_yaml_path=_agent_yaml_path(),
            judge=_FakeJudge(score=0.9),
            cases_path=Path("cases"),
        )
    assert controller._agent_yaml is not None
    assert controller._agent_yaml.name == "scheduling-v1"


def test_run_returns_results_full_pipeline(tmp_path: Path):
    shutil.copytree("cases/scheduling", tmp_path / "scheduling")
    mock_agent = _make_fake_maf_agent("Your appointment is confirmed.")
    with patch("hlsharness.maf_agent.build_maf_agent", return_value=mock_agent):
        controller = EvalController(
            agent_yaml_path=_agent_yaml_path(),
            judge=_FakeJudge(score=0.9),
            cases_path=tmp_path,
            stubs_path=Path("stubs"),
        )
        results = controller.run(categories=["functional"])

    assert len(results.cases) == 3
    assert all(r.agent == "scheduling-v1" for r in results.cases)
    assert results.passed is True


def test_upfront_validation_rejects_unknown_tool(tmp_path: Path):
    shutil.copytree("cases/scheduling", tmp_path / "scheduling")
    bad_case = {
        "id": "TC-BAD",
        "agent": "scheduling-v1",
        "category": "functional",
        "input": {"messages": [{"role": "user", "content": "Book me."}]},
        "tool_responses": {"undeclared_tool": {"result": "oops"}},
        "expected": {"outcome": "booked"},
    }
    (tmp_path / "scheduling" / "functional" / "TC-BAD.yaml").write_text(
        yaml.dump(bad_case), encoding="utf-8"
    )

    with pytest.raises(CaseValidationError, match="undeclared_tool"):
        _make_controller(tmp_path).run(categories=["functional"])


# -- Constructor validation ----------------------------------------------------


def test_raises_when_no_yaml_path_given():
    with pytest.raises(ValueError, match="agent_yaml_path"):
        EvalController(judge=_FakeJudge(), cases_path=Path("cases"))


def test_raises_when_no_judge_given():
    with pytest.raises(ValueError, match="judge"):
        EvalController(agent_yaml_path=_agent_yaml_path(), cases_path=Path("cases"))


def test_raises_when_no_cases_path_given():
    with pytest.raises(ValueError, match="cases_path"):
        with patch("hlsharness.maf_agent.build_maf_agent", return_value=None):
            EvalController(agent_yaml_path=_agent_yaml_path(), judge=_FakeJudge())
