"""Cross-phase integration: a siege (F6) declared in phase 4 must not
progress or charge upkeep on its own declare-tick, only from the next
tick's phase 7 onward - the resolver defers merging phase 4's
sieges_started until after that tick's phase 7 has run. Unit-level
coverage of the declare/upkeep/erosion/ending mechanics themselves
lives in test_phase4.py and test_phase7.py; this file only exercises
the wiring through real engine.resolve() calls across several ticks.
"""

import shutil
from pathlib import Path

import yaml

from engine.resolve import load_state, resolve

REPO_ROOT = Path(__file__).resolve().parent.parent
FULL_TICK = REPO_ROOT / "tests" / "fixtures" / "full_tick"


def _dump(path: Path, data) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")


def _prepare(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    shutil.copytree(FULL_TICK, root)

    region_path = root / "world" / "regions" / "ring-2.yml"
    region = yaml.safe_load(region_path.read_text(encoding="utf-8"))
    region["fortification"] = 1
    _dump(region_path, region)

    moves_dir = root / "moves" / "tick-1"
    _dump(moves_dir / "force-1.yml", {
        "actor": "force-1", "tick": 1, "origin": "agent",
        "orders": [{"action": "siege", "from": "ring-1", "to": "ring-2", "count": 1}],
    })
    _dump(moves_dir / "force-2.yml", {
        "actor": "force-2", "tick": 1, "origin": "agent", "orders": [],
    })
    _dump(moves_dir / "force-3.yml", {
        "actor": "force-3", "tick": 1, "origin": "agent", "orders": [],
    })
    return root


def test_siege_does_not_progress_on_its_own_declare_tick(tmp_path):
    root = _prepare(tmp_path)
    state = resolve(root, root / "moves" / "tick-1", seed=20260706)

    assert state["sieges"] == {
        "ring-2": {
            "attacker": "force-1", "defender": "force-2",
            "from": "ring-1", "units": 1, "ticks_elapsed": 0,
        }
    }
    assert state["regions"]["ring-1"]["units"] == 2  # 3 - 1 committed
    assert state["regions"]["ring-2"]["fortification"] == 1  # untouched this tick


def test_siege_progresses_and_erodes_on_schedule_then_ends(tmp_path):
    root = _prepare(tmp_path)
    resolve(root, root / "moves" / "tick-1", seed=20260706)  # declare

    empty_dir = root / "moves" / "tick-2"
    empty_dir.mkdir()
    state = resolve(root, empty_dir, seed=20260706)  # first real progress tick
    assert state["sieges"]["ring-2"]["ticks_elapsed"] == 1
    assert state["regions"]["ring-2"]["fortification"] == 1  # interval (2) not yet hit

    empty_dir_2 = root / "moves" / "tick-3"
    empty_dir_2.mkdir()
    state = resolve(root, empty_dir_2, seed=20260706)  # erosion interval hits

    assert "ring-2" not in state["sieges"]  # eroded to 0 -> siege ends
    assert state["regions"]["ring-2"]["fortification"] == 0
    assert state["regions"]["ring-1"]["units"] == 3  # committed unit returned home


def test_master_style_replay_is_byte_identical(tmp_path):
    first = _prepare(tmp_path / "first")
    second = _prepare(tmp_path / "second")
    for root in (first, second):
        resolve(root, root / "moves" / "tick-1", seed=20260706)
    tree = lambda r: {  # noqa: E731
        p.relative_to(r).as_posix(): p.read_bytes()
        for p in sorted(r.rglob("*")) if p.is_file()
    }
    assert tree(first) == tree(second)
    load_state(first)  # re-validates the written tree against world.schema.json
