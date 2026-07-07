import copy
from pathlib import Path

import pytest
import yaml

from engine.config import load_era_config
from engine.phase6_claim_loot import resolve_claim_loot
from engine.validate import validate_world

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "tick_reclamo_botin"
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


def _claim(actor, region, tick=1, origin="human"):
    return {
        "actor": actor, "tick": tick, "origin": origin,
        "orders": [{"action": "claim_loot", "region": region}],
    }


def test_fixture_world_is_schema_valid(state):
    validate_world(state)


def test_phase6_matches_expected_delta(state, moves):
    expected = _load(FIXTURE / "expected_delta.yml")
    assert resolve_claim_loot(state, moves, CONFIG, SEED) == expected


def test_phase6_is_pure(state, moves):
    state_snapshot = copy.deepcopy(state)
    moves_snapshot = copy.deepcopy(moves)
    first = resolve_claim_loot(state, moves, CONFIG, SEED)
    assert state == state_snapshot
    assert moves == moves_snapshot
    assert resolve_claim_loot(state, moves, CONFIG, SEED) == first


def test_applied_delta_keeps_world_schema_valid(state, moves):
    delta = resolve_claim_loot(state, moves, CONFIG, SEED)
    world = copy.deepcopy(state)
    for adventurer_id, change in delta["essence_changes"].items():
        world["adventurers"][adventurer_id]["essence"] += change
    for region_id, loot in delta["loot_changes"].items():
        world["regions"][region_id]["loot"] = loot
    validate_world(world)  # the arbiter is caged too


def test_collision_awards_exactly_one_claim_under_any_seed(state, moves):
    # the winner may differ by seed, but the pot is claimed exactly once
    for seed in (SEED, SEED + 1, SEED + 2):
        delta = resolve_claim_loot(state, moves, CONFIG, seed)
        assert sum(delta["essence_changes"].values()) == 3
        assert len(delta["essence_changes"]) == 1
        assert delta["loot_changes"] == {"ring-3": None}


def test_expired_loot_is_not_claimable(state):
    # arm-1-b loot expired at tick 0; resolving tick 1
    working = copy.deepcopy(state)
    working["adventurers"]["adventurer-sago"]["position"] = "arm-1-b"
    delta = resolve_claim_loot(working, [_claim("adventurer-sago", "arm-1-b")], CONFIG, SEED)
    assert delta["essence_changes"] == {}
    assert "no active loot" in delta["rejected_orders"][0]["reason"]


def test_loot_expiring_this_tick_is_still_claimable(state):
    # boundary: expires_tick == resolving tick -> claimable
    working = copy.deepcopy(state)
    working["adventurers"]["adventurer-sago"]["position"] = "arm-1-b"
    working["regions"]["arm-1-b"]["loot"]["expires_tick"] = 1
    delta = resolve_claim_loot(working, [_claim("adventurer-sago", "arm-1-b")], CONFIG, SEED)
    assert delta["essence_changes"] == {"adventurer-sago": 2}
    assert delta["loot_changes"] == {"arm-1-b": None}


def test_claim_from_elsewhere_rejected(state):
    delta = resolve_claim_loot(state, [_claim("adventurer-sago", "arm-1-b")], CONFIG, SEED)
    assert delta["essence_changes"] == {}
    assert "is not present in arm-1-b" in delta["rejected_orders"][0]["reason"]


def test_unknown_region_rejected(state):
    delta = resolve_claim_loot(state, [_claim("adventurer-sago", "atlantis")], CONFIG, SEED)
    assert "atlantis" in delta["rejected_orders"][0]["reason"]


def test_dead_actor_rejected(state):
    delta = resolve_claim_loot(state, [_claim("adventurer-ghost", "ring-3")], CONFIG, SEED)
    assert delta["essence_changes"] == {}
    assert "no living adventurer entity" in delta["rejected_orders"][0]["reason"]


def test_non_claim_orders_are_not_phase6_business(state):
    batch = {
        "actor": "adventurer-sago", "tick": 1, "origin": "human",
        "orders": [{"action": "move_units", "from": "ring-3", "to": "ring-1", "count": 1}],
    }
    delta = resolve_claim_loot(state, [batch], CONFIG, SEED)
    assert delta == {"essence_changes": {}, "loot_changes": {}, "rejected_orders": []}
