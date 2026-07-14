"""Assembles the LLM-facing context for one force's tick decision.

Perfect information (docs/intent.md, "Información"): every force sees the
full ``/world/`` state and the complete ``/moves/`` history. Rival
*personas* are never part of this - only their observed orders are. That
asymmetry is preserved simply by never loading another force's persona
file here; only the requesting force's own persona is ever read.
"""

import re
from pathlib import Path

import yaml

from engine.resolve import load_state

_TICK_DIR = re.compile(r"^tick-(\d+)$")


def load_move_history(state_dir: Path, upto_tick: int) -> list[dict]:
    """All resolved batches from tick 1 through *upto_tick*, tick then actor order."""
    moves_root = Path(state_dir) / "moves"
    if not moves_root.exists():
        return []

    tick_dirs = []
    for entry in moves_root.iterdir():
        match = _TICK_DIR.match(entry.name)
        if entry.is_dir() and match and int(match.group(1)) <= upto_tick:
            tick_dirs.append((int(match.group(1)), entry))
    tick_dirs.sort(key=lambda pair: pair[0])

    history = []
    for _, tick_dir in tick_dirs:
        for move_file in sorted(tick_dir.glob("*.yml")):
            try:
                batch = yaml.safe_load(move_file.read_text(encoding="utf-8"))
            except yaml.YAMLError:
                continue
            if isinstance(batch, dict):
                history.append(batch)
    return history


def build_context(state_dir, force_id: str) -> dict:
    """World state + full move history for the tick *force_id* must now decide.

    Raises ``KeyError`` if *force_id* is not a living force in the current
    state - this client speaks for forces only, never the adventurer (that
    seat is human-controlled by design, docs/intent.md "aventurero").
    """
    state_dir = Path(state_dir)
    state = load_state(state_dir)
    if force_id not in state["forces"]:
        raise KeyError(f"unknown force: {force_id}")
    return {
        "tick": state["tick"] + 1,
        "force_id": force_id,
        "state": state,
        "history": load_move_history(state_dir, state["tick"]),
    }
