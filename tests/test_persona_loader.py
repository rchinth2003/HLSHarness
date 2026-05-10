"""Unit tests for PersonaLoader — no Azure credentials required."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from hlsharness.persona_loader import Persona, PersonaLoader, UnknownPersonaError


def _write_persona(directory: Path, data: dict) -> None:
    path = directory / f"{data['id']}.yaml"
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(data, f)


# ── load_all ──────────────────────────────────────────────────────────────────


def test_load_all_returns_all_personas(tmp_path: Path):
    _write_persona(
        tmp_path, {"id": "p1", "age": 34, "language": "english", "insurance": "uninsured"}
    )
    _write_persona(
        tmp_path, {"id": "p2", "age": 45, "language": "spanish", "insurance": "medicaid"}
    )

    personas = PersonaLoader().load_all(tmp_path)

    assert set(personas.keys()) == {"p1", "p2"}


def test_load_all_parses_required_fields(tmp_path: Path):
    _write_persona(
        tmp_path,
        {"id": "adult", "age": 41, "language": "english", "insurance": "commercial"},
    )

    persona = PersonaLoader().load_all(tmp_path)["adult"]

    assert persona.id == "adult"
    assert persona.age == 41
    assert persona.language == "english"
    assert persona.insurance == "commercial"


def test_load_all_defaults_location_to_urban(tmp_path: Path):
    _write_persona(
        tmp_path, {"id": "p1", "age": 34, "language": "english", "insurance": "uninsured"}
    )

    persona = PersonaLoader().load_all(tmp_path)["p1"]

    assert persona.location == "urban"


def test_load_all_reads_optional_location(tmp_path: Path):
    _write_persona(
        tmp_path,
        {
            "id": "rural",
            "age": 52,
            "language": "english",
            "insurance": "commercial",
            "location": "rural",
        },
    )

    persona = PersonaLoader().load_all(tmp_path)["rural"]

    assert persona.location == "rural"


def test_load_all_reads_care_context(tmp_path: Path):
    _write_persona(
        tmp_path,
        {
            "id": "p1",
            "age": 34,
            "language": "english",
            "insurance": "uninsured",
            "care_context": "Seeking specialist care",
        },
    )

    persona = PersonaLoader().load_all(tmp_path)["p1"]

    assert persona.care_context == "Seeking specialist care"


def test_load_all_raises_file_not_found_for_missing_dir(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        PersonaLoader().load_all(tmp_path / "does_not_exist")


def test_load_all_raises_for_missing_required_field(tmp_path: Path):
    # Missing 'insurance'
    _write_persona(tmp_path, {"id": "bad", "age": 34, "language": "english"})

    with pytest.raises(ValueError, match="insurance"):
        PersonaLoader().load_all(tmp_path)


# ── resolve ───────────────────────────────────────────────────────────────────


def test_resolve_returns_correct_persona(tmp_path: Path):
    _write_persona(
        tmp_path, {"id": "target", "age": 79, "language": "english", "insurance": "medicare"}
    )

    persona = PersonaLoader().resolve("target", tmp_path)

    assert isinstance(persona, Persona)
    assert persona.id == "target"
    assert persona.age == 79


def test_resolve_raises_unknown_persona_error_for_bad_id(tmp_path: Path):
    _write_persona(
        tmp_path, {"id": "real", "age": 34, "language": "english", "insurance": "uninsured"}
    )

    with pytest.raises(UnknownPersonaError, match="ghost"):
        PersonaLoader().resolve("ghost", tmp_path)


# ── real personas/ directory ──────────────────────────────────────────────────


def test_real_personas_directory_loads_nine_entries():
    personas = PersonaLoader().load_all(Path("personas"))
    assert len(personas) == 9


def test_real_persona_uninsured_english_adult():
    persona = PersonaLoader().resolve("uninsured_english_adult", Path("personas"))
    assert persona.age == 34
    assert persona.insurance == "uninsured"
    assert persona.language == "english"


def test_real_persona_commercial_english_rural_has_location():
    persona = PersonaLoader().resolve("commercial_english_rural", Path("personas"))
    assert persona.location == "rural"


def test_real_persona_ids_match_filenames():
    """Every persona YAML's id field must match its filename stem."""
    for path in Path("personas").glob("*.yaml"):
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert data["id"] == path.stem, f"{path.name}: id mismatch"
