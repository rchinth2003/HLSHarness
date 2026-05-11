"""SolutionManifest — loader and validator for solution.yaml.

solution.yaml declares a named multi-agent solution: which agents participate,
whether each runs live or stubbed, and solution-level pass thresholds.

Example::

    solution: prior-auth-v1
    agents:
      - name: scheduling-v1
        stub: false
      - name: billing-v1
        stub: false
      - name: referral-v1
        stub: true
    thresholds:
      functional: 0.85
      safety: 1.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from hlsharness.loader import VALID_CATEGORIES


@dataclass
class AgentEntry:
    """A single agent declaration within a solution manifest."""

    name: str
    stub: bool = False


@dataclass
class SolutionManifest:
    """Parsed and validated representation of a ``solution.yaml`` file.

    Parameters
    ----------
    solution:   Unique name for this multi-agent solution.
    agents:     Ordered list of participating agents.
    thresholds: Per-category pass-rate thresholds for L2 rollup scoring.
                Merges over the harness defaults when SolutionController runs.
    """

    solution: str
    agents: list[AgentEntry]
    thresholds: dict[str, float] = field(default_factory=dict)

    # ── factory ──────────────────────────────────────────────────────────────

    @classmethod
    def load(cls, path: Path) -> SolutionManifest:
        """Parse a ``solution.yaml`` file and return a ``SolutionManifest``.

        Raises
        ------
        ValueError
            If required fields (``solution``, ``agents``) are missing or
            ``agents`` is empty.
        """
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{path}: solution.yaml must be a YAML mapping")

        solution = data.get("solution")
        if not solution:
            raise ValueError(f"{path}: missing required field 'solution'")

        raw_agents = data.get("agents")
        if not raw_agents:
            raise ValueError(f"{path}: 'agents' must be a non-empty list")

        agents = [
            AgentEntry(
                name=str(a["name"]),
                stub=bool(a.get("stub", False)),
            )
            for a in raw_agents
        ]

        thresholds = {str(k): float(v) for k, v in data.get("thresholds", {}).items()}

        return cls(solution=solution, agents=agents, thresholds=thresholds)

    # ── validation ───────────────────────────────────────────────────────────

    def validate(self, cases_path: Path, stubs_path: Path | None = None) -> None:
        """Validate the manifest against the filesystem.

        Checks (all errors collected, raised together):

        1. Every agent name resolves to ``cases/{name}/agent.yaml``.
        2. Every ``stub: true`` agent has at least one fixture file under
           ``stubs/{name}/``.
        3. Every threshold key is a recognised eval category.

        Parameters
        ----------
        cases_path:
            Root of the ``cases/`` directory tree.
        stubs_path:
            Root of the ``stubs/`` directory tree. Defaults to
            ``cases_path.parent / "stubs"``.

        Raises
        ------
        CaseValidationError
            When any validation check fails. All errors are collected and
            reported together.
        """
        from hlsharness.controller import CaseValidationError

        effective_stubs = stubs_path if stubs_path is not None else cases_path.parent / "stubs"
        errors: list[str] = []

        for entry in self.agents:
            agent_yaml = cases_path / entry.name / "agent.yaml"
            if not agent_yaml.exists():
                errors.append(f"agent '{entry.name}': agent.yaml not found at {agent_yaml}")

            if entry.stub:
                stub_dir = effective_stubs / entry.name
                if not stub_dir.exists() or not any(stub_dir.rglob("*.yaml")):
                    errors.append(
                        f"agent '{entry.name}': stub=true but no fixture files found under {stub_dir}"
                    )

        for category in self.thresholds:
            if category not in VALID_CATEGORIES:
                errors.append(
                    f"threshold key '{category}' is not a recognised category "
                    f"(known: {sorted(VALID_CATEGORIES)})"
                )

        if errors:
            from hlsharness.controller import CaseValidationError

            raise CaseValidationError("\n".join(errors))
