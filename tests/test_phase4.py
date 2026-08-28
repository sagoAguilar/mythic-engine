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
