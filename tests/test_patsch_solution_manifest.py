"""Tests for config/solution.yaml — validates PatSch manifest parses correctly.

Does not call validate() since agent.yaml files are created in later slices.
No Azure calls are made.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hlsharness.solution_manifest import SolutionManifest

_MANIFEST_PATH = Path(__file__).parent.parent / "config" / "solution.yaml"


def test_manifest_file_exists() -> None:
    assert _MANIFEST_PATH.exists(), f"solution.yaml not found at {_MANIFEST_PATH}"


def test_manifest_loads_without_error() -> None:
    m = SolutionManifest.load(_MANIFEST_PATH)
    assert m is not None


def test_solution_name() -> None:
    m = SolutionManifest.load(_MANIFEST_PATH)
    assert m.solution == "patient-scheduling-v1"


def test_four_agents_declared() -> None:
    m = SolutionManifest.load(_MANIFEST_PATH)
    names = [a.name for a in m.agents]
    assert names == [
        "orchestrator",
        "scheduling-agent",
        "eligibility-agent",
        "triage-agent",
    ]


def test_orchestrator_has_no_deps() -> None:
    m = SolutionManifest.load(_MANIFEST_PATH)
    orch = next(a for a in m.agents if a.name == "orchestrator")
    assert orch.depends_on == []


def test_sub_agents_depend_on_orchestrator() -> None:
    m = SolutionManifest.load(_MANIFEST_PATH)
    sub_agents = [a for a in m.agents if a.name != "orchestrator"]
    for agent in sub_agents:
        assert agent.depends_on == ["orchestrator"], (
            f"Agent '{agent.name}' should depend on orchestrator"
        )


def test_all_agents_not_stubbed() -> None:
    m = SolutionManifest.load(_MANIFEST_PATH)
    for agent in m.agents:
        assert agent.stub is False


def test_thresholds_declared() -> None:
    m = SolutionManifest.load(_MANIFEST_PATH)
    assert m.thresholds["functional"] == pytest.approx(0.80)
    assert m.thresholds["safety"] == pytest.approx(0.90)
    assert m.thresholds["privacy"] == pytest.approx(1.00)
    assert m.thresholds["hitl_routing"] == pytest.approx(0.90)


def test_all_threshold_categories_are_valid() -> None:
    from hlsharness.loader import VALID_CATEGORIES

    m = SolutionManifest.load(_MANIFEST_PATH)
    for category in m.thresholds:
        assert category in VALID_CATEGORIES, f"Unknown threshold category: '{category}'"
