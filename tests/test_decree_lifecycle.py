"""Cross-tick integration for decree/surge_recruit's streak (F7): the
persisted surge_streak on a force entity must escalate across
consecutive ticks of use and reset the moment a tick passes without it -
real engine.resolve() calls, not just the phase-3 unit tests in
test_phase3.py, since the streak's persistence is resolve.py's wiring
to get right, not phase 3's.
"""

import shutil
from pathlib import Path

import yaml

from engine.resolve import resolve

REPO_ROOT = Path(__file__).resolve().parent.parent
FULL_TICK = REPO_ROOT / "tests" / "fixtures" / "full_tick"


def _dump(path: Path, data) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")


def _prepare(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    shutil.copytree(FULL_TICK, root)

    force_path = root / "world" / "forces" / "force-1.yml"
    force = yaml.safe_load(force_path.read_text(encoding="utf-8"))
    force["essence"] = 100
    _dump(force_path, force)

    for tick in (1, 2, 3, 4):
        moves_dir = root / "moves" / f"tick-{tick}"
        moves_dir.mkdir(exist_ok=True)
        orders = (
            [{"action": "decree", "kind": "surge_recruit",
              "region": "capital-1", "count": 1}]
            if tick != 3 else []
        )
        _dump(moves_dir / "force-1.yml", {
            "actor": "force-1", "tick": tick, "origin": "agent", "orders": orders,
        })
        _dump(moves_dir / "force-2.yml", {
            "actor": "force-2", "tick": tick, "origin": "agent", "orders": [],
        })
        _dump(moves_dir / "force-3.yml", {
            "actor": "force-3", "tick": tick, "origin": "agent", "orders": [],
        })
    return root


def test_surge_streak_escalates_then_resets_after_a_skipped_tick(tmp_path):
    root = _prepare(tmp_path)

    state = resolve(root, root / "moves" / "tick-1", seed=20260706)
    assert state["forces"]["force-1"]["surge_streak"] == 1

    state = resolve(root, root / "moves" / "tick-2", seed=20260706)
    assert state["forces"]["force-1"]["surge_streak"] == 2

    state = resolve(root, root / "moves" / "tick-3", seed=20260706)  # no orders this tick
    assert state["forces"]["force-1"]["surge_streak"] == 0

    state = resolve(root, root / "moves" / "tick-4", seed=20260706)  # first use after the gap
    assert state["forces"]["force-1"]["surge_streak"] == 1
