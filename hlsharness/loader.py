"""CaseLoader — reads and validates YAML test cases from disk.

Test cases live under ``cases/{agent}/{category}/``, one YAML file per case.
The loader validates schema on load and surfaces clear errors for malformed files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

REQUIRED_TOP_LEVEL = {"id", "agent", "category", "input", "tool_responses", "expected"}
VALID_CATEGORIES = {"functional", "safety", "privacy", "equity", "operational"}


class CaseValidationError(Exception):
    """Raised when a YAML test case file fails schema validation."""


@dataclass
class TestCase:
    """A single evaluation test case loaded from a YAML file.

    Parameters
    ----------
    id:
        Unique identifier (e.g. ``"TC-001"``). Must be unique within a case suite.
    agent:
        Adapter name this case targets (e.g. ``"scheduling-v1"``). Must match
        the adapter's ``name`` property.
    category:
        Evaluation category: ``functional``, ``safety``, ``privacy``,
        ``equity``, or ``operational``.
    input:
        Dict with a ``messages`` list in OpenAI message format.
    tool_responses:
        Mapping of tool name → scripted response. Passed directly to
        ``ToolSimulator``.
    expected:
        Outcome expectations used by the Judge and analyzers. At minimum,
        include ``outcome`` (e.g. ``"booked"``) and optionally
        ``must_not_contain`` (list of strings the agent must not echo back).
    metadata:
        Demographic and contextual metadata for equity analysis.
        Recommended keys: ``patient_age``, ``language``, ``insurance``.
    """

    id: str
    agent: str
    category: str
    input: dict[str, object]
    tool_responses: dict[str, dict[str, object]]
    expected: dict[str, object]
    metadata: dict[str, object] = field(default_factory=dict)


class CaseLoader:
    """Loads and validates YAML test cases from the ``cases/`` directory tree.

    Directory convention::

        cases/
          {agent}/
            {category}/
              TC-001.yaml
              TC-002.yaml

    Examples
    --------
    Load all cases for the scheduling adapter:

    >>> loader = CaseLoader()
    >>> cases = loader.load(Path("cases"), agent="scheduling-v1")

    Load only safety cases:

    >>> cases = loader.load(Path("cases"), agent="scheduling-v1", category="safety")
    """

    def load(
        self,
        base_path: Path,
        agent: str | None = None,
        category: str | None = None,
    ) -> list[TestCase]:
        """Load all matching test cases from disk.

        Parameters
        ----------
        base_path:
            Root of the cases directory (typically ``Path("cases")``).
        agent:
            If provided, only cases whose YAML ``agent`` field matches are returned.
        category:
            If provided, only cases in that category subdirectory are returned.
            Must be one of: functional, safety, privacy, equity, operational.

        Returns
        -------
        list[TestCase]
            All matching cases, sorted by file path for deterministic ordering.

        Raises
        ------
        CaseValidationError
            If any matching YAML file fails schema validation.
        FileNotFoundError
            If ``base_path`` does not exist.
        """
        if not base_path.exists():
            raise FileNotFoundError(f"Cases directory not found: {base_path}")

        if category and category not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category '{category}'. Must be one of: {VALID_CATEGORIES}")

        pattern = "**/*.yaml"
        files = sorted(f for f in base_path.glob(pattern) if f.name != "manifest.yaml")

        cases = []
        for path in files:
            case = self._load_file(path)
            if agent and case.agent != agent:
                continue
            if category and case.category != category:
                continue
            cases.append(case)

        return cases

    def _load_file(self, path: Path) -> TestCase:
        """Parse and validate a single YAML file into a TestCase."""
        try:
            with path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            raise CaseValidationError(f"Malformed YAML in {path}: {exc}") from exc

        if not isinstance(data, dict):
            raise CaseValidationError(f"{path}: expected a YAML mapping, got {type(data).__name__}")

        missing = REQUIRED_TOP_LEVEL - data.keys()
        if missing:
            raise CaseValidationError(f"{path}: missing required fields: {missing}")

        if data["category"] not in VALID_CATEGORIES:
            raise CaseValidationError(
                f"{path}: invalid category '{data['category']}'. Must be one of: {VALID_CATEGORIES}"
            )

        if "messages" not in data.get("input", {}):
            raise CaseValidationError(f"{path}: 'input' must contain a 'messages' list")

        return TestCase(
            id=data["id"],
            agent=data["agent"],
            category=data["category"],
            input=data["input"],
            tool_responses=data["tool_responses"],
            expected=data["expected"],
            metadata=data.get("metadata", {}),
        )
