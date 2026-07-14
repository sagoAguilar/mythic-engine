"""Orchestrates one force's tick decision end to end.

build context -> prompt the model -> validate the result against the same
cage the engine uses (engine/validate.py) -> retry on rejection, feeding
the errors back to the model -> write the move file. A batch that never
passes validate_move is never written; that's the golden rule (CLAUDE.md)
enforced with a hard stop, not a best effort.

This is "the agent client (local machine in v1)" from docs/intent.md's
inventory: it produces a valid moves/tick-N/<force>.yml. Submitting that
file as a PR is a separate, manual step - this module does not touch git
or GitHub.
"""

import json
from pathlib import Path

import yaml

from engine.config import load_era_config
from engine.validate import ValidationError, validate_move

from .context import build_context
from .llm import LLMConfig, generate_orders
from .prompt import build_system_prompt, build_user_prompt

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "move.schema.json"


class ClientError(Exception):
    """The client could not produce a valid move within its retry budget."""


def _load_move_schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _resolve_persona(state_dir: Path, ctx: dict, persona_path) -> str:
    if persona_path is None:
        persona_path = state_dir / ctx["state"]["forces"][ctx["force_id"]]["persona"]
    return Path(persona_path).read_text(encoding="utf-8")


def generate_move(
    state_dir,
    force_id: str,
    *,
    persona_path=None,
    llm_config: LLMConfig | None = None,
    llm_client=None,
    max_attempts: int = 3,
) -> dict:
    """Produce one validated move batch for *force_id*. Does not write it.

    *persona_path* overrides the persona file the force's own world entry
    points to (``forces/<force_id>.yml``'s ``persona`` field); pass it
    explicitly only for testing or a deliberate one-off swap.
    """
    state_dir = Path(state_dir)
    config = load_era_config(state_dir / "world" / "era.yml")
    ctx = build_context(state_dir, force_id)
    persona = _resolve_persona(state_dir, ctx, persona_path)
    move_schema = _load_move_schema()
    llm_config = llm_config or LLMConfig()

    errors: list[str] = []
    for _ in range(max_attempts):
        system_prompt = build_system_prompt(persona)
        user_prompt = build_user_prompt(ctx, config, errors)
        orders = generate_orders(system_prompt, user_prompt, move_schema, llm_config, client=llm_client)
        batch = {"actor": force_id, "tick": ctx["tick"], "origin": "agent", "orders": orders}
        try:
            validate_move(batch, config)
            return batch
        except ValidationError as exc:
            errors = exc.errors

    raise ClientError(f"{force_id}: no valid move after {max_attempts} attempts: {errors}")


def write_move(state_dir, batch: dict) -> Path:
    """Write a validated batch to moves/tick-<N>/<actor>.yml."""
    out_dir = Path(state_dir) / "moves" / f"tick-{batch['tick']}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{batch['actor']}.yml"
    out_path.write_text(yaml.safe_dump(batch, sort_keys=False), encoding="utf-8")
    return out_path
