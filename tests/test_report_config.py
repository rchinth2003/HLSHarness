"""Unit tests for ReportConfig — no Azure credentials required."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from hlsharness.report_config import ReportConfig

# ── defaults() ────────────────────────────────────────────────────────────────


def test_defaults_returns_report_config() -> None:
    cfg = ReportConfig.defaults()
    assert isinstance(cfg, ReportConfig)


def test_defaults_org() -> None:
    assert ReportConfig.defaults().org == "Contoso Health"


def test_defaults_brand_color() -> None:
    assert ReportConfig.defaults().brand_color == "#0D3B66"


def test_defaults_title_template() -> None:
    assert ReportConfig.defaults().title_template == "{agent} — AI Quality Evaluation"


# ── load() ────────────────────────────────────────────────────────────────────


def test_load_all_fields(tmp_path: Path) -> None:
    cfg_file = tmp_path / "report_config.yaml"
    cfg_file.write_text(
        "org: Acme Health\nbrand_color: '#FF0000'\ntitle_template: '{agent} Report'\n",
        encoding="utf-8",
    )
    cfg = ReportConfig.load(cfg_file)
    assert cfg.org == "Acme Health"
    assert cfg.brand_color == "#FF0000"
    assert cfg.title_template == "{agent} Report"


def test_load_partial_overrides_only_specified_fields(tmp_path: Path) -> None:
    cfg_file = tmp_path / "report_config.yaml"
    cfg_file.write_text("org: Custom Org\n", encoding="utf-8")
    cfg = ReportConfig.load(cfg_file)
    assert cfg.org == "Custom Org"
    assert cfg.brand_color == "#0D3B66"  # default preserved


def test_load_unknown_keys_ignored(tmp_path: Path) -> None:
    cfg_file = tmp_path / "report_config.yaml"
    cfg_file.write_text("org: X\nunknown_key: ignored\n", encoding="utf-8")
    cfg = ReportConfig.load(cfg_file)
    assert cfg.org == "X"


def test_load_empty_file_returns_defaults(tmp_path: Path) -> None:
    cfg_file = tmp_path / "report_config.yaml"
    cfg_file.write_text("", encoding="utf-8")
    cfg = ReportConfig.load(cfg_file)
    assert cfg == ReportConfig.defaults()


def test_load_missing_file_raises_oserror(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        ReportConfig.load(tmp_path / "nonexistent.yaml")


def test_load_malformed_yaml_raises_value_error(tmp_path: Path) -> None:
    cfg_file = tmp_path / "report_config.yaml"
    cfg_file.write_text("org: [\n  unclosed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed YAML"):
        ReportConfig.load(cfg_file)


def test_load_non_mapping_yaml_raises_value_error(tmp_path: Path) -> None:
    cfg_file = tmp_path / "report_config.yaml"
    cfg_file.write_text("- item1\n- item2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must contain a YAML mapping"):
        ReportConfig.load(cfg_file)


# ── render_title() ────────────────────────────────────────────────────────────


def test_render_title_substitutes_agent() -> None:
    cfg = ReportConfig.defaults()
    result = cfg.render_title(agent="prior-auth-v1", date="2026-05-10")
    assert "prior-auth-v1" in result


def test_render_title_substitutes_date() -> None:
    cfg = ReportConfig(title_template="{agent} — {date}")
    result = cfg.render_title(agent="scheduling-v1", date="2026-05-10")
    assert result == "scheduling-v1 — 2026-05-10"


def test_render_title_default_template_does_not_require_date() -> None:
    cfg = ReportConfig.defaults()
    result = cfg.render_title(agent="my-agent", date="2026-05-10")
    assert "my-agent" in result


# ── immutability ──────────────────────────────────────────────────────────────


def test_report_config_is_frozen() -> None:
    cfg = ReportConfig.defaults()
    with pytest.raises(dataclasses.FrozenInstanceError):  # type: ignore[attr-defined]
        cfg.org = "mutated"  # type: ignore[misc]
