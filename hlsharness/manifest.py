"""AgentManifest — per-agent configuration schema, validation, and load/write.

A manifest YAML at ``cases/{agent}/manifest.yaml`` is the single source of truth
for an agent's eval configuration: tool definitions, categories, and pass-rate
thresholds.  ``EvalController`` reads it at run time; the onboarding CLI writes it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

_REQUIRED_FIELDS = {"agent", "description", "categories", "tools", "thresholds"}


class ManifestValidationError(Exception):
    """Raised when a manifest YAML file fails schema validation."""


@dataclass
class ManifestTool:
    """A single tool declared in an agent manifest.

    Parameters
    ----------
    name:
        Tool identifier — must match the adapter's ``ToolDefinition.name``.
    description:
        Natural-language description forwarded to the LLM.
    parameters:
        JSON Schema object (same shape as ``ToolDefinition.parameters``).
    """

    name: str
    description: str
    parameters: dict[str, object] = field(default_factory=dict)


@dataclass
class AgentManifest:
    """Per-agent eval configuration loaded from ``cases/{agent}/manifest.yaml``.

    Parameters
    ----------
    agent:
        Agent identifier, e.g. ``"prior-auth-v1"``.  Must match the adapter's
        ``name`` property and the ``cases/{agent}/`` directory.
    description:
        Human-readable description of the agent's purpose.
    categories:
        Evaluation categories enabled for this agent (e.g. ``["functional", "safety"]``).
    tools:
        Tool definitions declared by this agent.
    thresholds:
        Per-category pass-rate thresholds, e.g. ``{"safety": 0.9}``.
    system_prompt_hint:
        Optional system prompt seed used by ``AdapterScaffolder`` and
        ``SpecInterpreter``.  Empty string when not provided.
    """

    agent: str
    description: str
    categories: list[str]
    tools: list[ManifestTool]
    thresholds: dict[str, float]
    system_prompt_hint: str = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: Path) -> AgentManifest:
        """Load and validate a manifest from *path*.

        Raises
        ------
        ManifestValidationError
            If the file is missing required fields or contains invalid values.
        FileNotFoundError
            If *path* does not exist.
        """
        try:
            with path.open(encoding="utf-8") as fh:
                data: Any = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            raise ManifestValidationError(f"Malformed YAML in {path}: {exc}") from exc

        if not isinstance(data, dict):
            raise ManifestValidationError(
                f"{path}: expected a YAML mapping, got {type(data).__name__}"
            )

        missing = _REQUIRED_FIELDS - data.keys()
        if missing:
            raise ManifestValidationError(f"{path}: missing required fields: {sorted(missing)}")

        return cls._from_dict(data, path)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentManifest:
        """Construct an AgentManifest from a plain dict (e.g. parsed from LLM output).

        Raises
        ------
        ManifestValidationError
            If *data* is missing required fields or contains invalid values.
        """
        missing = _REQUIRED_FIELDS - data.keys()
        if missing:
            raise ManifestValidationError(f"Missing required fields: {sorted(missing)}")
        return cls._from_dict(data, Path("<from_dict>"))

    def write(self, path: Path) -> None:
        """Serialise this manifest to *path* as YAML.

        Creates parent directories if they do not exist.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = asdict(self)
        with path.open("w", encoding="utf-8") as fh:
            yaml.dump(raw, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @classmethod
    def _from_dict(cls, data: dict[str, Any], path: Path) -> AgentManifest:
        agent = cls._require_str(data, "agent", path)
        description = cls._require_str(data, "description", path)

        categories = data["categories"]
        if not isinstance(categories, list) or not all(isinstance(c, str) for c in categories):
            raise ManifestValidationError(f"{path}: 'categories' must be a list of strings")

        tools = cls._parse_tools(data["tools"], path)
        thresholds = cls._parse_thresholds(data["thresholds"], path)

        hint = data.get("system_prompt_hint", "")
        if not isinstance(hint, str):
            raise ManifestValidationError(f"{path}: 'system_prompt_hint' must be a string")

        return cls(
            agent=agent,
            description=description,
            categories=categories,
            tools=tools,
            thresholds=thresholds,
            system_prompt_hint=hint,
        )

    @staticmethod
    def _require_str(data: dict[str, Any], key: str, path: Path) -> str:
        value = data[key]
        if not isinstance(value, str) or not value.strip():
            raise ManifestValidationError(f"{path}: '{key}' must be a non-empty string")
        return value

    @staticmethod
    def _parse_tools(raw: Any, path: Path) -> list[ManifestTool]:
        if not isinstance(raw, list):
            raise ManifestValidationError(f"{path}: 'tools' must be a list")
        tools: list[ManifestTool] = []
        for i, item in enumerate(raw):
            if not isinstance(item, dict):
                raise ManifestValidationError(f"{path}: tools[{i}] must be a mapping")
            if "name" not in item or not isinstance(item["name"], str):
                raise ManifestValidationError(
                    f"{path}: tools[{i}] missing required string field 'name'"
                )
            if "description" not in item or not isinstance(item["description"], str):
                raise ManifestValidationError(
                    f"{path}: tools[{i}] missing required string field 'description'"
                )
            params = item.get("parameters", {})
            if not isinstance(params, dict):
                raise ManifestValidationError(f"{path}: tools[{i}].parameters must be a mapping")
            tools.append(
                ManifestTool(
                    name=item["name"],
                    description=item["description"],
                    parameters=params,
                )
            )
        return tools

    @staticmethod
    def _parse_thresholds(raw: Any, path: Path) -> dict[str, float]:
        if not isinstance(raw, dict):
            raise ManifestValidationError(f"{path}: 'thresholds' must be a mapping")
        thresholds: dict[str, float] = {}
        for key, value in raw.items():
            if not isinstance(key, str):
                raise ManifestValidationError(f"{path}: threshold key {key!r} must be a string")
            if not isinstance(value, (int, float)):
                raise ManifestValidationError(
                    f"{path}: threshold for '{key}' must be a number, got {type(value).__name__}"
                )
            thresholds[key] = float(value)
        return thresholds
