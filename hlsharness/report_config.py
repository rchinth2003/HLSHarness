"""ReportConfig — branding and layout settings for the PDF Evaluation Report.

Loaded from an optional ``report_config.yaml`` in the working directory.
All fields have sensible defaults so the report renders without any config file.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import yaml


@dataclasses.dataclass(frozen=True)
class ReportConfig:
    """Immutable branding config consumed by ReportRenderer."""

    org: str = "Contoso Health"
    brand_color: str = "#0D3B66"
    title_template: str = "{agent} — AI Quality Evaluation"

    # ── factories ──────────────────────────────────────────────────────────────

    @classmethod
    def defaults(cls) -> ReportConfig:
        """Return a ReportConfig with all defaults."""
        return cls()

    @classmethod
    def load(cls, path: Path) -> ReportConfig:
        """Load a ReportConfig from a YAML file.

        Unknown keys are silently ignored so future versions can add fields
        without breaking existing config files.

        Raises
        ------
        OSError
            If *path* does not exist or cannot be read.
        ValueError
            If the YAML is malformed or a field has the wrong type.
        """
        raw = path.read_text(encoding="utf-8")
        try:
            data: Any = yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            raise ValueError(f"Malformed YAML in {path}: {exc}") from exc

        if data is None:
            return cls()

        if not isinstance(data, dict):
            raise ValueError(f"{path} must contain a YAML mapping, got {type(data).__name__}")

        known = {f.name for f in dataclasses.fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in known}

        try:
            return cls(**kwargs)
        except TypeError as exc:
            raise ValueError(f"Invalid field in {path}: {exc}") from exc

    # ── helpers ────────────────────────────────────────────────────────────────

    def render_title(self, agent: str, date: str) -> str:
        """Expand *title_template* with agent name and date."""
        return self.title_template.format(agent=agent, date=date)
