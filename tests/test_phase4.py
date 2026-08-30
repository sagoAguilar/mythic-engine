import copy
from pathlib import Path

import pytest
import yaml

from engine.config import load_era_config
from engine.phase4_movement import resolve_movement
from engine.validate import validate_move, validate_world

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "tick_colision_espejo"
CONFIG = load_era_config(REPO_ROOT / "world" / "era.yml")
SEED = CONFIG.era.seed


def _load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.fixture()
def state():
    return _load(FIXTURE / "world.yml")


@pytest.fixture()
def moves():
    return [_load(p) for p in sorted((FIXTURE / "moves").glob("*.yml"))]


def test_fixture_inputs_are_schema_valid(state, moves):
    validate_world(state)
    for batch in moves:
        validate_move(batch, CONFIG)


def test_phase4_matches_expected_delta(state, moves):
    expected = _load(FIXTURE / "expected_delta.yml")
    assert resolve_movement(state, moves, CONFIG, SEED) == expected


def test_phase4_is_pure(state, moves):
    snapshot = copy.deepcopy(state)
    moves_snapshot = copy.deepcopy(moves)
    first = resolve_movement(state, moves, CONFIG, SEED)
    assert state == snapshot, "phase 4 must not mutate the input state"
    assert moves == moves_snapshot, "phase 4 must not mutate the input moves"
    assert resolve_movement(state, moves, CONFIG, SEED) == first


def test_phase4_depends_on_seed(state, moves):
    baseline = resolve_movement(state, moves, CONFIG, SEED)
    reordered = resolve_movement(state, moves, CONFIG, SEED + 1)
    ring3 = {c["region"]: c for c in baseline["pending_combats"]}["ring-3"]
    ring3_other = {c["region"]: c for c in reordered["pending_combats"]}["ring-3"]
    # same parties either way; only the seeded formula may reorder them
    assert sorted(p["actor"] for p in ring3["parties"]) == sorted(
        p["actor"] for p in ring3_other["parties"]
    )


def test_adventurer_cannot_attack(state, moves):
    batch = {
        "actor": "adventurer-sago",
        "tick": 1,
        "origin": "human",
        "orders": [
            {"action": "attack_region", "from": "arm-2-b", "to": "ring-2", "count": 1}
        ],
    }
    delta = resolve_movement(state, [batch], CONFIG, SEED)
    assert delta["pending_combats"] == []
    assert len(delta["rejected_orders"]) == 1
    assert "adventurer" in delta["rejected_orders"][0]["reason"]


def test_targeted_adventurer_attack_is_staged(state):
    # F4: explicit hunt declaration; adventurer-sago sits at arm-2-b
    batch = {
        "actor": "force-2",
        "tick": 1,
        "origin": "agent",
        "orders": [
            {
                "action": "attack_region",
                "from": "capital-2",
                "to": "arm-2-b",
                "count": 1,
                "target": "adventurer",
            }
        ],
    }
    delta = resolve_movement(state, [batch], CONFIG, SEED)
    assert delta["rejected_orders"] == []
    combats = {c["region"]: c for c in delta["pending_combats"]}
    assert combats["arm-2-b"]["parties"] == [
        {"actor": "force-2", "count": 1, "kind": "attack", "target": "adventurer"}
    ]


def _siege(actor, src, dst, count):
    return {
        "actor": actor, "tick": 1, "origin": "agent",
        "orders": [{"action": "siege", "from": src, "to": dst, "count": count}],
    }


def test_siege_commits_units_and_starts_a_record(state):
    # force-1 (ring-1) besieges force-2's fortified ring-2 next door
    working = copy.deepcopy(state)
    working["regions"]["ring-2"]["fortification"] = 1
    delta = resolve_movement(working, [_siege("force-1", "ring-1", "ring-2", 2)], CONFIG, SEED)
    assert delta["rejected_orders"] == []
    assert delta["unit_changes"] == {"ring-1": -2}
    assert delta["pending_combats"] == []  # no F1 duel - a siege never fights
    assert delta["sieges_started"] == {
        "ring-2": {
            "attacker": "force-1", "defender": "force-2",
            "from": "ring-1", "units": 2, "ticks_elapsed": 0,
        }
    }


def test_adventurer_cannot_siege(state):
    batch = _siege("adventurer-sago", "arm-2-b", "ring-2", 1)
    delta = resolve_movement(state, [batch], CONFIG, SEED)
    assert delta["sieges_started"] == {}
    assert "force-only" in delta["rejected_orders"][0]["reason"]


def test_siege_from_unowned_region_rejected(state):
    working = copy.deepcopy(state)
    working["regions"]["ring-2"]["fortification"] = 1
    delta = resolve_movement(working, [_siege("force-1", "ring-2", "ring-1", 1)], CONFIG, SEED)
    assert "not owned by force-1" in delta["rejected_orders"][0]["reason"]


def test_siege_exceeding_available_units_rejected(state):
    working = copy.deepcopy(state)
    working["regions"]["ring-2"]["fortification"] = 1
    delta = resolve_movement(working, [_siege("force-1", "ring-1", "ring-2", 99)], CONFIG, SEED)
    assert "exceed" in delta["rejected_orders"][0]["reason"]


def test_siege_of_non_adjacent_region_rejected(state):
    working = copy.deepcopy(state)
    working["regions"]["capital-2"]["fortification"] = 1
    delta = resolve_movement(working, [_siege("force-1", "ring-1", "capital-2", 1)], CONFIG, SEED)
    assert "not adjacent" in delta["rejected_orders"][0]["reason"]


def test_siege_of_own_or_neutral_region_rejected(state):
    working = copy.deepcopy(state)
    delta = resolve_movement(
        working,
        [_siege("force-1", "capital-1", "arm-1-a", 1),  # own
         _siege("force-1", "ring-1", "ring-3", 1)],       # neutral
        CONFIG, SEED,
    )
    assert len(delta["rejected_orders"]) == 2
    assert all("not hostile" in r["reason"] for r in delta["rejected_orders"])


def test_siege_of_unfortified_region_rejected(state):
    # ring-2's fortification is 0 in the base fixture - nothing to erode
    delta = resolve_movement(state, [_siege("force-1", "ring-1", "ring-2", 1)], CONFIG, SEED)
    assert "fortification" in delta["rejected_orders"][0]["reason"]


def test_siege_of_already_besieged_region_rejected(state):
    working = copy.deepcopy(state)
    working["regions"]["ring-2"]["fortification"] = 1
    working["sieges"] = {
        "ring-2": {"attacker": "force-3", "defender": "force-2",
                   "from": "arm-3-a", "units": 1, "ticks_elapsed": 4}
    }
    delta = resolve_movement(working, [_siege("force-1", "ring-1", "ring-2", 1)], CONFIG, SEED)
    assert "already under siege" in delta["rejected_orders"][0]["reason"]
    assert delta["sieges_started"] == {}


def test_two_sieges_on_the_same_region_in_one_tick_second_rejected(state):
    working = copy.deepcopy(state)
    working["regions"]["ring-1"]["fortification"] = 1
    batch = {
        "actor": "force-2", "tick": 1, "origin": "agent",
        "orders": [
            {"action": "siege", "from": "ring-2", "to": "ring-1", "count": 1},
            {"action": "siege", "from": "ring-2", "to": "ring-1", "count": 1},
        ],
    }
    delta = resolve_movement(working, [batch], CONFIG, SEED)
    assert len(delta["sieges_started"]) == 1
    assert delta["rejected_orders"] == [
        {"actor": "force-2", "index": 1, "reason": "siege: ring-1 is already under siege"}
    ]


def test_attack_on_own_or_neutral_region_rejected(state):
    batch = {
        "actor": "force-3",
        "tick": 1,
        "origin": "agent",
        "orders": [
            {"action": "attack_region", "from": "capital-3", "to": "arm-3-a", "count": 1},
            {"action": "attack_region", "from": "arm-3-a", "to": "ring-3", "count": 1},
        ],
    }
    delta = resolve_movement(state, [batch], CONFIG, SEED)
    assert delta["pending_combats"] == []
    assert [r["index"] for r in delta["rejected_orders"]] == [0, 1]


# --- guild capabilities: swift_march + sanctuary (phase 4) --------------
# NOTE: the fixture-backed variants (tick_gremio_capacidades) were lost with
# an untracked stash; the synthetic-state tests below fully cover the same
# swift_march/sanctuary behavior against the shared tick_colision_espejo map.


def _adv(state, *, capabilities=(), essence=5, position="arm-2-b"):
    """A batch-issuing copy of *state* whose adventurer has *capabilities*."""
    working = copy.deepcopy(state)
    adv = working["adventurers"]["adventurer-sago"]
    adv["capabilities"] = list(capabilities)
    adv["essence"] = essence
    adv["position"] = position
    return working


def _batch(*orders):
    return {"actor": "adventurer-sago", "tick": 1, "origin": "agent",
            "orders": list(orders)}


def test_swift_march_single_hop_is_allowed(state):
    working = _adv(state, capabilities=["swift_march"], essence=5)
    batch = _batch({"action": "swift_march", "from": "arm-2-b", "to": "ring-2", "count": 1})
    delta = resolve_movement(working, [batch], CONFIG, SEED)
    assert delta["rejected_orders"] == []
    assert delta["adventurer_moves"] == {"adventurer-sago": "ring-2"}
    assert delta["essence_changes"] == {"adventurer-sago": -CONFIG.guild.capabilities.costs.swift_march}


def test_swift_march_beyond_two_hops_is_rejected(state):
    # capital-1 is 3+ hops from arm-2-b
    working = _adv(state, capabilities=["swift_march"], essence=5)
    batch = _batch({"action": "swift_march", "from": "arm-2-b", "to": "capital-1", "count": 1})
    delta = resolve_movement(working, [batch], CONFIG, SEED)
    assert delta["adventurer_moves"] == {}
    assert delta["essence_changes"] == {}
    assert "not reachable" in delta["rejected_orders"][0]["reason"]


def test_swift_march_without_capability_is_rejected(state):
    working = _adv(state, capabilities=[], essence=5)
    batch = _batch({"action": "swift_march", "from": "arm-2-b", "to": "ring-1", "count": 1})
    delta = resolve_movement(working, [batch], CONFIG, SEED)
    assert delta["adventurer_moves"] == {}
    assert "capability not unlocked" in delta["rejected_orders"][0]["reason"]


def test_swift_march_insufficient_essence_is_rejected(state):
    working = _adv(state, capabilities=["swift_march"], essence=0)
    batch = _batch({"action": "swift_march", "from": "arm-2-b", "to": "ring-1", "count": 1})
    delta = resolve_movement(working, [batch], CONFIG, SEED)
    assert delta["adventurer_moves"] == {}
    assert delta["essence_changes"] == {}
    assert "essence" in delta["rejected_orders"][0]["reason"]


def test_swift_march_and_move_units_conflict_on_the_move_budget(state):
    # one move per tick: swift_march spends it, the follow-on move_units bounces
    working = _adv(state, capabilities=["swift_march"], essence=5)
    batch = _batch(
        {"action": "swift_march", "from": "arm-2-b", "to": "ring-1", "count": 1},
        {"action": "move_units", "from": "ring-1", "to": "ring-2", "count": 1},
    )
    delta = resolve_movement(working, [batch], CONFIG, SEED)
    assert delta["adventurer_moves"] == {"adventurer-sago": "ring-1"}
    assert [r["index"] for r in delta["rejected_orders"]] == [1]
    assert "already moved" in delta["rejected_orders"][0]["reason"]


def test_sanctuary_sets_immunity_and_charges(state):
    working = _adv(state, capabilities=["sanctuary"], essence=5)
    batch = _batch({"action": "sanctuary"})
    delta = resolve_movement(working, [batch], CONFIG, SEED)
    assert delta["rejected_orders"] == []
    expected_until = 1 + CONFIG.guild.capabilities.sanctuary_ticks - 1
    assert delta["sanctuary_until"] == {"adventurer-sago": expected_until}
    assert delta["essence_changes"] == {"adventurer-sago": -CONFIG.guild.capabilities.costs.sanctuary}


def test_sanctuary_without_capability_is_rejected(state):
    working = _adv(state, capabilities=[], essence=5)
    batch = _batch({"action": "sanctuary"})
    delta = resolve_movement(working, [batch], CONFIG, SEED)
    assert delta["sanctuary_until"] == {}
    assert "capability not unlocked" in delta["rejected_orders"][0]["reason"]


def test_sanctuary_twice_charges_once(state):
    working = _adv(state, capabilities=["sanctuary"], essence=5)
    batch = _batch({"action": "sanctuary"}, {"action": "sanctuary"})
    delta = resolve_movement(working, [batch], CONFIG, SEED)
    assert delta["essence_changes"] == {"adventurer-sago": -CONFIG.guild.capabilities.costs.sanctuary}
    assert [r["index"] for r in delta["rejected_orders"]] == [1]
    assert "already invoked" in delta["rejected_orders"][0]["reason"]


def test_force_cannot_invoke_capability_actions(state):
    batch = {"actor": "force-1", "tick": 1, "origin": "agent",
             "orders": [{"action": "sanctuary"},
                        {"action": "swift_march", "from": "capital-1", "to": "ring-1", "count": 1}]}
    delta = resolve_movement(state, [batch], CONFIG, SEED)
    assert [r["index"] for r in delta["rejected_orders"]] == [0, 1]
    assert all("adventurer-only" in r["reason"] for r in delta["rejected_orders"])
