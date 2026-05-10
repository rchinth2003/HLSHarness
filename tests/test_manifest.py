"""Unit tests for AgentManifest — load, validate, write, round-trip.

No Azure calls; all tests operate on tmp_path fixtures.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from hlsharness.manifest import AgentManifest, ManifestTool, ManifestValidationError

# ── Fixture helpers ─────────────────────────────────────────────────────────


def _write_yaml(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(data, fh)


def _valid_data() -> dict[str, object]:
    return {
        "agent": "prior-auth-v1",
        "description": "Prior authorization agent",
        "categories": ["functional", "safety"],
        "tools": [
            {
                "name": "check_coverage",
                "description": "Check insurance coverage",
                "parameters": {"type": "object", "properties": {}},
            }
        ],
        "thresholds": {"functional": 0.8, "safety": 0.9},
    }


# ── Load: happy path ─────────────────────────────────────────────────────────


def test_load_populates_all_fields(tmp_path: Path) -> None:
    p = tmp_path / "manifest.yaml"
    _write_yaml(p, _valid_data())

    m = AgentManifest.load(p)

    assert m.agent == "prior-auth-v1"
    assert m.description == "Prior authorization agent"
    assert m.categories == ["functional", "safety"]
    assert len(m.tools) == 1
    assert m.tools[0].name == "check_coverage"
    assert m.thresholds == {"functional": 0.8, "safety": 0.9}
    assert m.system_prompt_hint == ""


def test_load_optional_system_prompt_hint(tmp_path: Path) -> None:
    data = _valid_data()
    data["system_prompt_hint"] = "You are a PA specialist."
    p = tmp_path / "manifest.yaml"
    _write_yaml(p, data)

    m = AgentManifest.load(p)

    assert m.system_prompt_hint == "You are a PA specialist."


def test_load_empty_tools_list(tmp_path: Path) -> None:
    data = _valid_data()
    data["tools"] = []
    p = tmp_path / "manifest.yaml"
    _write_yaml(p, data)

    m = AgentManifest.load(p)

    assert m.tools == []


def test_load_integer_threshold_coerced_to_float(tmp_path: Path) -> None:
    data = _valid_data()
    data["thresholds"] = {"functional": 1}  # type: ignore[assignment]
    p = tmp_path / "manifest.yaml"
    _write_yaml(p, data)

    m = AgentManifest.load(p)

    assert m.thresholds["functional"] == 1.0
    assert isinstance(m.thresholds["functional"], float)


def test_load_tool_without_parameters_defaults_to_empty_dict(tmp_path: Path) -> None:
    data = _valid_data()
    data["tools"] = [{"name": "simple_tool", "description": "No params"}]
    p = tmp_path / "manifest.yaml"
    _write_yaml(p, data)

    m = AgentManifest.load(p)

    assert m.tools[0].parameters == {}


def test_load_file_not_found_raises() -> None:
    with pytest.raises(FileNotFoundError):
        AgentManifest.load(Path("/nonexistent/manifest.yaml"))


# ── Load: missing required fields ────────────────────────────────────────────


@pytest.mark.parametrize(
    "missing_field", ["agent", "description", "categories", "tools", "thresholds"]
)
def test_load_missing_required_field_raises(tmp_path: Path, missing_field: str) -> None:
    data = _valid_data()
    del data[missing_field]
    p = tmp_path / "manifest.yaml"
    _write_yaml(p, data)

    with pytest.raises(ManifestValidationError, match=missing_field):
        AgentManifest.load(p)


# ── Load: invalid field types ─────────────────────────────────────────────────


def test_load_non_mapping_raises(tmp_path: Path) -> None:
    p = tmp_path / "manifest.yaml"
    _write_yaml(p, ["not", "a", "dict"])

    with pytest.raises(ManifestValidationError, match="expected a YAML mapping"):
        AgentManifest.load(p)


def test_load_invalid_threshold_type_raises(tmp_path: Path) -> None:
    data = _valid_data()
    data["thresholds"] = {"functional": "high"}  # type: ignore[assignment]
    p = tmp_path / "manifest.yaml"
    _write_yaml(p, data)

    with pytest.raises(ManifestValidationError, match="threshold for 'functional'"):
        AgentManifest.load(p)


def test_load_categories_not_list_raises(tmp_path: Path) -> None:
    data = _valid_data()
    data["categories"] = "functional"  # type: ignore[assignment]
    p = tmp_path / "manifest.yaml"
    _write_yaml(p, data)

    with pytest.raises(ManifestValidationError, match="categories"):
        AgentManifest.load(p)


def test_load_tools_not_list_raises(tmp_path: Path) -> None:
    data = _valid_data()
    data["tools"] = "check_coverage"  # type: ignore[assignment]
    p = tmp_path / "manifest.yaml"
    _write_yaml(p, data)

    with pytest.raises(ManifestValidationError, match="tools"):
        AgentManifest.load(p)


def test_load_tool_missing_name_raises(tmp_path: Path) -> None:
    data = _valid_data()
    data["tools"] = [{"description": "No name field"}]
    p = tmp_path / "manifest.yaml"
    _write_yaml(p, data)

    with pytest.raises(ManifestValidationError, match="name"):
        AgentManifest.load(p)


def test_load_tool_missing_description_raises(tmp_path: Path) -> None:
    data = _valid_data()
    data["tools"] = [{"name": "my_tool"}]
    p = tmp_path / "manifest.yaml"
    _write_yaml(p, data)

    with pytest.raises(ManifestValidationError, match="description"):
        AgentManifest.load(p)


def test_load_empty_agent_string_raises(tmp_path: Path) -> None:
    data = _valid_data()
    data["agent"] = "   "
    p = tmp_path / "manifest.yaml"
    _write_yaml(p, data)

    with pytest.raises(ManifestValidationError, match="agent"):
        AgentManifest.load(p)


# ── Write + round-trip ────────────────────────────────────────────────────────


def test_write_creates_parent_dirs(tmp_path: Path) -> None:
    manifest = AgentManifest(
        agent="test-agent",
        description="Test",
        categories=["functional"],
        tools=[],
        thresholds={"functional": 0.8},
    )
    dest = tmp_path / "nested" / "dir" / "manifest.yaml"

    manifest.write(dest)

    assert dest.exists()


def test_round_trip_produces_equal_manifest(tmp_path: Path) -> None:
    p = tmp_path / "manifest.yaml"
    data = _valid_data()
    data["system_prompt_hint"] = "You are helpful."
    _write_yaml(p, data)

    original = AgentManifest.load(p)
    out = tmp_path / "out" / "manifest.yaml"
    original.write(out)
    reloaded = AgentManifest.load(out)

    assert reloaded.agent == original.agent
    assert reloaded.description == original.description
    assert reloaded.categories == original.categories
    assert reloaded.thresholds == original.thresholds
    assert reloaded.system_prompt_hint == original.system_prompt_hint
    assert len(reloaded.tools) == len(original.tools)
    assert reloaded.tools[0].name == original.tools[0].name
    assert reloaded.tools[0].description == original.tools[0].description


def test_round_trip_multiple_tools(tmp_path: Path) -> None:
    manifest = AgentManifest(
        agent="scheduling-v1",
        description="Scheduling agent",
        categories=["functional", "safety", "privacy", "equity"],
        tools=[
            ManifestTool(name="search_available_slots", description="Find slots"),
            ManifestTool(name="book_appointment", description="Book slot"),
            ManifestTool(name="cancel_appointment", description="Cancel"),
        ],
        thresholds={"functional": 0.8, "safety": 0.9, "privacy": 1.0, "equity": 0.9},
    )
    p = tmp_path / "manifest.yaml"
    manifest.write(p)
    reloaded = AgentManifest.load(p)

    assert [t.name for t in reloaded.tools] == [
        "search_available_slots",
        "book_appointment",
        "cancel_appointment",
    ]
