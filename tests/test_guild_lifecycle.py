"""Cross-tick integration for the Adventurers' Guild (intent.md point 9):
the full spawn -> accept -> resolve -> reward -> capability arc through
real engine.resolve() calls, not just the phase-8/9 unit tests. This is
what exercises resolve.py's wiring - stake charged on accept, the
reward/reputation routed to the adventurer pool, the completed tier
persisted onto adventurer.guild, the granted capability appended to
adventurer.capabilities, and (next tick) that capability actually
spendable via swift_march - none of which any single-phase test covers.

The design under test is the adventurer-gated full ladder: guild boards
spawn only with exactly one living adventurer, accept and completion are
necessarily different ticks (phase 8 accepts after it verifies, so a
same-tick claim can never be instantly rewarded), and Bronze pays via
the seeded coin-flip while completing the tier still confers swift_march
whether the coin hit or missed.
"""

import hashlib
import shutil
from pathlib import Path

import yaml

from engine.config import load_era_config
from engine.resolve import resolve

REPO_ROOT = Path(__file__).resolve().parent.parent
FULL_TICK = REPO_ROOT / "tests" / "fixtures" / "full_tick"
CONFIG = load_era_config(REPO_ROOT / "world" / "era.yml")
SEED = 20260706


def _dump(path: Path, data) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")


def _bronze_coin_hit(tick: int, quest_id: str) -> bool:
    """Mirror phase 8's Bronze coin exactly (even -> hit)."""
    coin = int(hashlib.sha256(
        f"{SEED}:{tick}:adventurer-sago:{quest_id}".encode("utf-8")
    ).hexdigest(), 16)
    return coin % 2 == 0


def _quiet_forces(moves_dir: Path) -> None:
    for actor in ("force-1", "force-2", "force-3"):
        _dump(moves_dir / f"{actor}.yml", {
            "actor": actor, "tick": int(moves_dir.name.split("-")[1]),
            "origin": "agent", "orders": [],
        })


def _prepare(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    shutil.copytree(FULL_TICK, root)

    # Sole living adventurer: drop the elder's tick-1 spawn so phase 9's
    # guild boards fire (they no-op with zero or several adventurers).
    (root / "moves" / "tick-1" / "adventurer-elder.yml").unlink()

    # A Bronze travel board on force-1's tablón, unclaimed, targeting the
    # adventurer's own start region so a single stationary tick completes
    # it. Reward 0 at spawn: the phase-8 coin pays Bronze.
    active_dir = root / "world" / "quests" / "active"
    active_dir.mkdir(parents=True, exist_ok=True)
    _dump(active_dir / "travel-0-1.yml", {
        "id": "travel-0-1", "type": "travel", "tier": "minor",
        "eligibility": "adventurer", "reward": 0, "stake": 1, "deadline": 5,
        "max_claimants": 1, "claimed_by": [], "progress": {},
        "params": {"region": "arm-2-b", "force": "force-1",
                   "guild_tier": "bronze"},
    })

    for tick in (1, 2, 3):
        moves_dir = root / "moves" / f"tick-{tick}"
        moves_dir.mkdir(exist_ok=True)
        _quiet_forces(moves_dir)
    return root


def _guild_slots(state: dict) -> set:
    return {
        (q["params"]["force"], q["params"]["guild_tier"])
        for q in state["quests"]["active"].values()
        if "guild_tier" in q.get("params", {})
    }


def test_guild_full_arc_spawn_accept_reward_capability(tmp_path):
    root = _prepare(tmp_path)

    # --- tick 1: accept the board; phase 9 spawns the rest of the ladder --
    _dump(root / "moves" / "tick-1" / "adventurer-sago.yml", {
        "actor": "adventurer-sago", "tick": 1, "origin": "human",
        "orders": [{"action": "accept_quest", "quest_id": "travel-0-1"}],
    })
    state = resolve(root, root / "moves" / "tick-1", seed=SEED)

    sago = state["adventurers"]["adventurer-sago"]
    assert state["quests"]["active"]["travel-0-1"]["claimed_by"] == ["adventurer-sago"]
    assert sago["essence"] == 5 - 1  # stake charged on accept
    assert "travel-0-1" not in state["quests"]["resolved"]  # no same-tick reward
    # sole adventurer at reputation 0: only Bronze is accessible, and
    # force-1's Bronze slot is taken, so phase 9 fills force-2 and force-3.
    assert ("force-2", "bronze") in _guild_slots(state)
    assert ("force-3", "bronze") in _guild_slots(state)

    # --- tick 2: stationary on the target -> completion, reward, capability
    _dump(root / "moves" / "tick-2" / "adventurer-sago.yml", {
        "actor": "adventurer-sago", "tick": 2, "origin": "human", "orders": [],
    })
    state = resolve(root, root / "moves" / "tick-2", seed=SEED)

    sago = state["adventurers"]["adventurer-sago"]
    assert state["quests"]["resolved"]["travel-0-1"]["status"] == "success"
    assert sago["guild"] == {"force-1": {"completed": ["bronze"]}}
    assert "swift_march" in sago["capabilities"]  # Bronze -> the shared capability

    hit = _bronze_coin_hit(2, "travel-0-1")
    expected_essence = (5 - 1) + (
        CONFIG.guild.rewards.essence.bronze_hit if hit
        else CONFIG.guild.rewards.essence.bronze_miss
    )
    assert sago["essence"] == expected_essence
    assert sago["reputation"]["force-1"] == (
        CONFIG.guild.rewards.reputation.bronze if hit else 0
    )

    chronicle = (root / "chronicle" / "tick-2.md").read_text(encoding="utf-8")
    assert "gremio:bronze@force-1" in chronicle
    assert "capacidad:+swift_march" in chronicle
    assert "rango:force-1=bronze" in chronicle

    # --- tick 3: the just-earned capability is spendable across ticks -----
    essence_before = sago["essence"]
    _dump(root / "moves" / "tick-3" / "adventurer-sago.yml", {
        "actor": "adventurer-sago", "tick": 3, "origin": "human",
        "orders": [{"action": "swift_march", "from": "arm-2-b",
                    "to": "arm-2-a", "count": 1}],  # a genuine 2-hop reach
    })
    state = resolve(root, root / "moves" / "tick-3", seed=SEED)

    sago = state["adventurers"]["adventurer-sago"]
    assert sago["position"] == "arm-2-a"
    assert sago["essence"] == essence_before - CONFIG.guild.capabilities.costs.swift_march
