"""Cross-phase integration for the Guild's Bronze/travel quest (F9): a
real multi-tick engine.resolve() playthrough, not just the phase-8/9
unit tests - this is what proves the standing-pool spawn (phase 9) and
the coin-flip resolution (phase 8) actually compose correctly through
the resolver, across several ticks, the way test_siege_lifecycle.py and
test_decree_lifecycle.py already do for their own features.
"""

import shutil
from pathlib import Path

import yaml

from engine.resolve import resolve

REPO_ROOT = Path(__file__).resolve().parent.parent
FULL_TICK = REPO_ROOT / "tests" / "fixtures" / "full_tick"


def _dump(path: Path, data) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")


def _quiet_forces(root: Path, tick: int) -> None:
    moves_dir = root / "moves" / f"tick-{tick}"
    moves_dir.mkdir(parents=True, exist_ok=True)
    for actor in ("force-1", "force-2", "force-3"):
        _dump(moves_dir / f"{actor}.yml", {
            "actor": actor, "tick": tick, "origin": "agent", "orders": [],
        })


def test_bronze_travel_quest_spawns_is_accepted_and_completes(tmp_path):
    root = tmp_path / "repo"
    shutil.copytree(FULL_TICK, root)

    _quiet_forces(root, 1)
    _dump(root / "moves" / "tick-1" / "adventurer-sago.yml", {
        "actor": "adventurer-sago", "tick": 1, "origin": "human", "orders": [],
    })
    state = resolve(root, root / "moves" / "tick-1", seed=20260706)

    travels = {
        qid: q for qid, q in state["quests"]["active"].items() if q["type"] == "travel"
    }
    assert len(travels) == 3
    assert {q["params"]["force"] for q in travels.values()} == {
        "force-1", "force-2", "force-3",
    }
    # force-2's board quest targets arm-3-b, reachable from sago's arm-2-b
    # in exactly 3 hops (ring-2 -> ring-3 -> arm-3-b), landing on its
    # deadline (tick 1 + travel_deadline 3 = 4) exactly
    quest_id, quest = next(
        (qid, q) for qid, q in travels.items() if q["params"]["force"] == "force-2"
    )
    assert quest["params"]["region"] == "arm-3-b"
    assert quest["deadline"] == 4

    for tick, dest in ((2, "ring-2"), (3, "ring-3"), (4, "arm-3-b")):
        _quiet_forces(root, tick)
        moves_dir = root / "moves" / f"tick-{tick}"
        orders = [{"action": "move_units", "from": None, "to": dest, "count": 1}]
        orders[0]["from"] = state["adventurers"]["adventurer-sago"]["position"]
        if tick == 2:
            orders.append({"action": "accept_quest", "quest_id": quest_id})
        _dump(moves_dir / "adventurer-sago.yml", {
            "actor": "adventurer-sago", "tick": tick, "origin": "human", "orders": orders,
        })
        state = resolve(root, moves_dir, seed=20260706)

    assert quest_id in state["quests"]["resolved"]
    assert state["quests"]["resolved"][quest_id]["status"] == "success"
    assert quest_id not in state["quests"]["active"]
    # coin-flip landed either way, but never a net loss versus the stake
    assert state["adventurers"]["adventurer-sago"]["essence"] >= 5 - 1
