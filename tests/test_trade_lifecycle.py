"""Cross-phase integration for trade (F8): a real engine.resolve() call,
not just the phase-6 unit tests in test_phase6.py - this is what would
have caught the essence_changes routing bug where phase 6's delta now
mixes adventurer and force actor keys (trade genuinely transfers to a
force, unlike claim_loot which only ever paid the adventurer) and
resolve.py must route each key to the right pool, not just index
blindly into working["adventurers"].
"""

import shutil
from pathlib import Path

import yaml

from engine.resolve import resolve

REPO_ROOT = Path(__file__).resolve().parent.parent
FULL_TICK = REPO_ROOT / "tests" / "fixtures" / "full_tick"


def _dump(path: Path, data) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")


def test_successful_trade_moves_essence_and_reputation_through_resolve(tmp_path):
    root = tmp_path / "repo"
    shutil.copytree(FULL_TICK, root)

    adventurer_path = root / "world" / "forces" / "adventurer-sago.yml"
    adventurer = yaml.safe_load(adventurer_path.read_text(encoding="utf-8"))
    adventurer["reputation"]["force-2"] = 10  # meets reputation.thresholds.trade
    _dump(adventurer_path, adventurer)

    # neutralize the other actors so force-2's essence math stays
    # predictable: only yield/upkeep and the trade itself move it
    for actor in ("force-1", "force-2", "force-3"):
        _dump(root / "moves" / "tick-1" / f"{actor}.yml", {
            "actor": actor, "tick": 1, "origin": "agent", "orders": [],
        })
    # adventurer-sago sits at arm-2-b (force-2's) - sha256(seed:1:
    # adventurer-sago:force-2) rolls 40, under both ring (50) and arm (75)
    # success thresholds, so this lands regardless of exact tier lookup
    _dump(root / "moves" / "tick-1" / "adventurer-sago.yml", {
        "actor": "adventurer-sago", "tick": 1, "origin": "human",
        "orders": [{"action": "trade", "region": "arm-2-b"}],
    })

    state = resolve(root, root / "moves" / "tick-1", seed=20260706)

    assert state["adventurers"]["adventurer-sago"]["essence"] == 5 - 3
    assert state["adventurers"]["adventurer-sago"]["reputation"]["force-2"] == 12
    # force-2: 10 units -> yield 6 - upkeep floor(10/5)=2, plus trade's +3
    assert state["forces"]["force-2"]["essence"] == 10 + (6 - 2) + 3

    chronicle = (root / "chronicle" / "tick-1.md").read_text(encoding="utf-8")
    assert "trade:+@force-2" in chronicle
