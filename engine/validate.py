"""Schema validation for move batches and world state, wrapping jsonschema.

The JSON Schemas under schema/ pin structure: allowed keys, exact action
shapes, value types. Anything that docs/intent.md declares as an era.yml
parameter — order caps, fortification cap, reputation scale — is NOT
frozen into the schemas; this module enforces those against the loaded
:class:`~engine.config.EraConfig` instead.
"""

import json
from pathlib import Path

import jsonschema

from engine.config import EraConfig

_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"


class ValidationError(Exception):
    """Data does not conform to its schema. ``errors`` lists every violation."""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors if errors is not None else [message]


def _validator(schema_name: str) -> jsonschema.Draft202012Validator:
    schema = json.loads((_SCHEMA_DIR / schema_name).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


_MOVE_VALIDATOR = _validator("move.schema.json")
_WORLD_VALIDATOR = _validator("world.schema.json")


def _check(validator: jsonschema.Draft202012Validator, data: object, label: str) -> None:
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    if errors:
        messages = [
            f"{'.'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in errors
        ]
        raise ValidationError(
            f"{label} failed schema validation:\n" + "\n".join(messages), messages
        )


def validate_move(data: object, config: EraConfig) -> None:
    """Validate one move batch against move.schema.json plus era.yml caps.

    Raises :class:`ValidationError` on any schema violation or when the
    batch exceeds the actor's order cap (orders.cap_force /
    orders.cap_adventurer from era.yml).
    """
    _check(_MOVE_VALIDATOR, data, "move batch")
    if data["actor"].startswith("adventurer-"):
        cap = config.orders.cap_adventurer
    else:
        cap = config.orders.cap_force
    if len(data["orders"]) > cap:
        raise ValidationError(
            f"move batch: {len(data['orders'])} orders exceeds cap {cap} "
            f"for actor {data['actor']}"
        )


def validate_world(data: object) -> None:
    """Validate an assembled world state against world.schema.json.

    Raises :class:`ValidationError` on any schema violation.
    """
    _check(_WORLD_VALIDATOR, data, "world state")
