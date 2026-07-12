#!/usr/bin/env python3
"""Thin shell invoked by .github/workflows/resolve.yml.

Reads the current tick from world/tick.txt, resolves tick + 1 by
consuming moves/tick-<tick+1>/ - present or empty, NPC substitution
covers absence per docs/intent.md - and lets engine.resolve() write
the next state and chronicle in place. All adjudication logic lives
in engine/, tested offline under tests/; this script only wires paths
and the seed together, so the workflow itself carries no game logic.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from engine import resolve  # noqa: E402
from engine.config import load_era_config  # noqa: E402


def run(repo_root: Path) -> dict:
    config = load_era_config(repo_root / "world" / "era.yml")
    current_tick = int(
        (repo_root / "world" / "tick.txt").read_text(encoding="utf-8").strip()
    )
    moves_dir = repo_root / "moves" / f"tick-{current_tick + 1}"
    return resolve(repo_root, moves_dir, config.era.seed)


def main() -> None:
    state = run(REPO_ROOT)
    print(f"resolved tick {state['tick']}")


if __name__ == "__main__":
    main()
