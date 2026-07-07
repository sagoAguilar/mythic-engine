import copy
from pathlib import Path

import pytest
import yaml

from engine.config import load_era_config
from engine.phase2_spawn import resolve_spawn
from engine.validate import validate_world

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "tick_spawn_aventurero"
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


def test_fixture_world_is_schema_valid(state):
    validate_world(state)


def test_phase2_matches_expected_delta(state, moves):
    expected = _load(FIXTURE / "expected_delta.yml")
    assert resolve_spawn(state, moves, CONFIG, SEED) == expected


def test_spawned_entities_are_schema_valid(state, moves):
    delta = resolve_spawn(state, moves, CONFIG, SEED)
    world = copy.deepcopy(state)
    world["adventurers"].update(delta["spawned"])
    validate_world(world)  # the arbiter is caged too


def test_phase2_is_pure(state, moves):
    state_snapshot = copy.deepcopy(state)
    moves_snapshot = copy.deepcopy(moves)
    first = resolve_spawn(state, moves, CONFIG, SEED)
    assert state == state_snapshot
    assert moves == moves_snapshot
    assert resolve_spawn(state, moves, CONFIG, SEED) == first


def _spawn_batch(actor, origin, name="Someone"):
    return {
        "actor": actor,
        "tick": 1,
        "origin": "human",
        "orders": [
            {"action": "spawn_adventurer", "name": name, "origin": origin}
        ],
    }


def test_tick0_symmetric_world_spawns_only_on_neutrals(state):
    # M3: spawnables at tick 0 are the 9 neutrals. With every force tied
    # at 1 region there is no strictly least-dominant force, so no force
    # territory is spawnable.
    state = copy.deepcopy(state)
    for rid, region in state["regions"].items():
        if rid.startswith("capital-"):
            region["owner"] = "force-" + rid.removeprefix("capital-")
        else:
            region["owner"] = None

    rejected = resolve_spawn(state, [_spawn_batch("adventurer-x", "capital-1")], CONFIG, SEED)
    assert rejected["spawned"] == {}
    assert len(rejected["rejected_orders"]) == 1

    accepted = resolve_spawn(state, [_spawn_batch("adventurer-x", "ring-2")], CONFIG, SEED)
    assert list(accepted["spawned"]) == ["adventurer-x"]
    assert accepted["rejected_orders"] == []


def test_living_entity_blocks_spawn(state):
    state = copy.deepcopy(state)
    state["adventurers"]["adventurer-sago"] = {
        "id": "adventurer-sago", "name": "Wanderer",
        "controller": "github:sago", "essence": 5, "position": "ring-3",
        "units": 1, "reputation": {f"force-{i}": 0 for i in (1, 2, 3)},
        "capabilities": [], "personal_quest": {"type": "survive", "target": "era"},
    }
    delta = resolve_spawn(state, [_spawn_batch("adventurer-sago", "ring-2")], CONFIG, SEED)
    assert delta["spawned"] == {}
    assert "already has a living entity" in delta["rejected_orders"][0]["reason"]


def test_unknown_origin_region_rejected(state):
    delta = resolve_spawn(state, [_spawn_batch("adventurer-x", "atlantis")], CONFIG, SEED)
    assert delta["spawned"] == {}
    assert "atlantis" in delta["rejected_orders"][0]["reason"]


def test_non_spawn_orders_are_not_phase2_business(state):
    batch = {
        "actor": "force-2", "tick": 1, "origin": "agent",
        "orders": [{"action": "fortify", "region": "capital-2"}],
    }
    delta = resolve_spawn(state, [batch], CONFIG, SEED)
    assert delta == {"spawned": {}, "rejected_orders": []}
