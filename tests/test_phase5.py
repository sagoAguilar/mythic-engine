import copy
import math
from pathlib import Path

import pytest
import yaml

from engine.config import load_era_config
from engine.phase5_combat import resolve_combat
from engine.validate import validate_world

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "tick_combate_simple"
CONFIG = load_era_config(REPO_ROOT / "world" / "era.yml")
SEED = CONFIG.era.seed


def _load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.fixture()
def world():
    return _load(FIXTURE / "world.yml")


@pytest.fixture()
def state(world):
    working = copy.deepcopy(world)
    working["pending_combats"] = _load(FIXTURE / "pending_combats.yml")
    return working


def test_fixture_world_is_schema_valid(world):
    validate_world(world)


def test_phase5_matches_expected_delta(state):
    expected = _load(FIXTURE / "expected_delta.yml")
    assert resolve_combat(state, [], CONFIG, SEED) == expected


def test_phase5_is_pure(state):
    snapshot = copy.deepcopy(state)
    first = resolve_combat(state, [], CONFIG, SEED)
    assert state == snapshot
    assert resolve_combat(state, [], CONFIG, SEED) == first


def test_no_pending_combats_is_a_quiet_tick(world):
    working = copy.deepcopy(world)
    working["pending_combats"] = []
    delta = resolve_combat(working, [], CONFIG, SEED)
    assert delta["unit_changes"] == {}
    assert delta["owner_changes"] == {}
    assert delta["combats"] == []
    assert delta["combat_regions"] == []


def _hunt(state, count, actor="force-1", region="arm-2-b"):
    working = copy.deepcopy(state)
    working["pending_combats"] = [{
        "region": region,
        "parties": [
            {"actor": actor, "count": count, "kind": "attack", "target": "adventurer"}
        ],
    }]
    return working


def test_hunt_kills_and_killer_collects_when_controlling(state):
    # 2 hunters vs garrison 1: kill lands, ladder captures arm-2-b,
    # killer controls the death region -> collects the loot deposit
    working = _hunt(state, count=2)
    delta = resolve_combat(working, [], CONFIG, SEED)

    assert delta["adventurer_deaths"] == [
        {"id": "adventurer-sago", "region": "arm-2-b", "killer": "force-1"}
    ]
    essence = state["adventurers"]["adventurer-sago"]["essence"]
    burn = math.ceil(essence * CONFIG.adventurer.loot_burn_fraction)
    assert delta["essence_changes"] == {"force-1": essence - burn}
    assert delta["loot_changes"] == {}
    assert delta["owner_changes"] == {"arm-2-b": "force-1"}
    assert delta["graveyard_additions"] == [{
        "id": "adventurer-sago", "name": "Wanderer",
        "controller": "github:sagoAguilar",
        "died_tick": 1, "era": CONFIG.era.number, "titles": [],
    }]
    assert "arm-2-b" in delta["combat_regions"]


def test_hunt_kills_but_loot_lies_when_killer_lacks_control(state):
    # 1 hunter vs garrison 1: tie favors the defender, hunters annihilated,
    # but the kill landed; the deposit lies as claimable loot for M ticks
    working = _hunt(state, count=1)
    delta = resolve_combat(working, [], CONFIG, SEED)

    assert delta["adventurer_deaths"] == [
        {"id": "adventurer-sago", "region": "arm-2-b", "killer": "force-1"}
    ]
    essence = state["adventurers"]["adventurer-sago"]["essence"]
    burn = math.ceil(essence * CONFIG.adventurer.loot_burn_fraction)
    assert delta["essence_changes"] == {}
    assert delta["loot_changes"] == {
        "arm-2-b": {
            "essence": essence - burn,
            "expires_tick": 1 + CONFIG.adventurer.loot_dissipation_ticks,
        }
    }
    assert delta["owner_changes"] == {}


def test_hunt_misses_when_adventurer_moved_away(state):
    # post-move dodge: the adventurer left arm-2-b this tick; the hunt
    # party still fights its ladder step as a normal attack
    working = _hunt(state, count=2)
    working["adventurers"]["adventurer-sago"]["position"] = "capital-2"
    delta = resolve_combat(working, [], CONFIG, SEED)

    assert delta["adventurer_deaths"] == []
    assert delta["graveyard_additions"] == []
    assert delta["loot_changes"] == {}
    assert delta["owner_changes"] == {"arm-2-b": "force-1"}


def test_hunt_in_own_territory_merges_and_collects(state):
    # force-2 hunts the adventurer sheltering in force-2's own region:
    # no combat round, units merge, kill lands, controller collects
    working = _hunt(state, count=1, actor="force-2")
    delta = resolve_combat(working, [], CONFIG, SEED)

    assert delta["adventurer_deaths"] == [
        {"id": "adventurer-sago", "region": "arm-2-b", "killer": "force-2"}
    ]
    essence = state["adventurers"]["adventurer-sago"]["essence"]
    burn = math.ceil(essence * CONFIG.adventurer.loot_burn_fraction)
    assert delta["essence_changes"] == {"force-2": essence - burn}
    assert delta["unit_changes"] == {"arm-2-b": 1}  # merged, not fought
    assert delta["combats"] == [{"region": "arm-2-b", "rounds": []}]


def test_applied_delta_keeps_world_schema_valid(state, world):
    delta = resolve_combat(state, [], CONFIG, SEED)
    result = copy.deepcopy(world)
    for rid, change in delta["unit_changes"].items():
        result["regions"][rid]["units"] += change
    for rid, owner in delta["owner_changes"].items():
        result["regions"][rid]["owner"] = owner
    for rid, loot in delta["loot_changes"].items():
        result["regions"][rid]["loot"] = loot
    for fid, change in delta["essence_changes"].items():
        result["forces"][fid]["essence"] += change
    for death in delta["adventurer_deaths"]:
        del result["adventurers"][death["id"]]
    result["graveyard"].extend(delta["graveyard_additions"])
    result["combats_last_tick"] = delta["combat_regions"]
    validate_world(result)  # the arbiter is caged too
