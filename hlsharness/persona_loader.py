"""PersonaLoader — loads shared patient demographic profiles from personas/.

Personas decouple patient demographics from individual test cases. Equity
cases reference a persona by ID; the loader resolves it to a typed Persona.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


class UnknownPersonaError(Exception):
    """Raised when a persona ID cannot be resolved in the personas directory."""


@dataclass
class Persona:
    """A reusable patient demographic profile.

    Parameters
    ----------
    id:
        Unique identifier matching the YAML filename (without extension).
    age:
        Patient age in years.
    language:
        Primary language (e.g. ``"english"``, ``"spanish"``).
    insurance:
        Insurance type (e.g. ``"commercial"``, ``"medicaid"``, ``"uninsured"``).
    location:
        Geographic context; defaults to ``"urban"``.
    care_context:
        Brief description of the patient's care situation.
    """

    id: str
    age: int
    language: str
    insurance: str
    location: str = "urban"
    care_context: str = field(default="")


class PersonaLoader:
    """Loads and resolves Persona objects from a ``personas/`` directory.

    YAML files in the directory must declare: id, age, language, insurance.
    Optional fields: location (default ``"urban"``), care_context.
    """

    def load_all(self, personas_path: Path) -> dict[str, Persona]:
        """Load every YAML in ``personas_path`` and return a mapping of id → Persona.

        Parameters
        ----------
        personas_path:
            Directory containing persona YAML files.

        Raises
        ------
        FileNotFoundError
            If the directory does not exist.
        ValueError
            If any YAML file is missing required fields.
        """
        if not personas_path.exists():
            raise FileNotFoundError(f"Personas directory not found: {personas_path}")

        personas: dict[str, Persona] = {}
        for path in sorted(personas_path.glob("*.yaml")):
            persona = self._load_file(path)
            personas[persona.id] = persona
        return personas

    def resolve(self, persona_id: str, personas_path: Path) -> Persona:
        """Resolve a persona ID to a Persona object.

        Parameters
        ----------
        persona_id:
            The ``id`` value declared in the persona YAML.
        personas_path:
            Directory to search for persona YAMLs.

        Raises
        ------
        UnknownPersonaError
            If no persona with that ID exists in the directory.
        """
        personas = self.load_all(personas_path)
        if persona_id not in personas:
            raise UnknownPersonaError(
                f"Unknown persona '{persona_id}'. Available: {sorted(personas.keys())}"
            )
        return personas[persona_id]

    def _load_file(self, path: Path) -> Persona:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise ValueError(f"{path}: expected a YAML mapping, got {type(data).__name__}")

        missing = {"id", "age", "language", "insurance"} - data.keys()
        if missing:
            raise ValueError(f"{path}: missing required persona fields: {missing}")

        return Persona(
            id=str(data["id"]),
            age=int(data["age"]),
            language=str(data["language"]),
            insurance=str(data["insurance"]),
            location=str(data.get("location", "urban")),
            care_context=str(data.get("care_context", "")),
        )
