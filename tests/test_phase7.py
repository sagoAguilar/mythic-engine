import copy
from pathlib import Path

import pytest
import yaml

from engine.config import load_era_config
from engine.phase7_yield import resolve_yield
from engine.validate import validate_world

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "tick_rendimiento"
CONFIG = load_era_config(REPO_ROOT / "world" / "era.yml")
SEED = CONFIG.era.seed


def _load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.fixture()
def state():
    return _load(FIXTURE / "world.yml")


def test_fixture_world_is_schema_valid(state):
    validate_world(state)


def test_phase7_matches_expected_delta(state):
    expected = _load(FIXTURE / "expected_delta.yml")
    assert resolve_yield(state, [], CONFIG, SEED) == expected


def test_phase7_is_pure(state):
    snapshot = copy.deepcopy(state)
    first = resolve_yield(state, [], CONFIG, SEED)
    assert state == snapshot
    assert resolve_yield(state, [], CONFIG, SEED) == first


def test_applied_delta_keeps_world_schema_valid(state):
    delta = resolve_yield(state, [], CONFIG, SEED)
    world = copy.deepcopy(state)
    for force_id, change in delta["essence_changes"].items():
        world["forces"][force_id]["essence"] += change
    for region_id, loot in delta["loot_changes"].items():
        world["regions"][region_id]["loot"] = loot
    validate_world(world)  # the arbiter is caged too


def test_zero_unit_owned_regions_still_pay(state):
    delta = resolve_yield(state, [], CONFIG, SEED)
    # force-3 holds capital-3 (2) plus two scorched 0-unit regions
    # (arm-3-a: 1, ring-3: 2); ownership, not garrison, earns yield
    assert delta["essence_changes"]["force-3"] == 5


def test_yield_reads_region_state_not_hardcoded_values(state):
    working = copy.deepcopy(state)
    working["regions"]["arm-1-a"]["yield"] = 7
    delta = resolve_yield(working, [], CONFIG, SEED)
    # force-1 holds 6 units total -> floor(6/5)=1 upkeep nets against yield
    assert delta["essence_changes"]["force-1"] == (2 + 7 + 2) - 1


def test_upkeep_is_free_below_the_divisor(state):
    # force-3 holds 2 units total; floor(2/5)=0, pure yield, no deduction
    delta = resolve_yield(state, [], CONFIG, SEED)
    assert delta["essence_changes"]["force-3"] == 5


def test_upkeep_scales_with_total_garrison_not_cached_units(state):
    # phase 7 must recompute from region state, not trust forces[x].units,
    # since that cache isn't refreshed until resolve()'s final assembly -
    # same discipline phase 8's attrition check already uses.
    working = copy.deepcopy(state)
    working["forces"]["force-1"]["units"] = 999  # stale/wrong cache
    working["regions"]["capital-1"]["units"] += 10  # force-1: 6 -> 16 units
    delta = resolve_yield(working, [], CONFIG, SEED)
    # yield unaffected by the extra garrison; upkeep now floor(16/5)=3
    assert delta["essence_changes"]["force-1"] == 5 - 3


def test_upkeep_never_touches_the_adventurer(state):
    # the adventurer owns no regions, so units_owned never gets populated
    # for them regardless of their personal unit count
    delta = resolve_yield(state, [], CONFIG, SEED)
    assert "adventurer-sago" not in delta["essence_changes"]


def test_loot_expiring_this_tick_is_not_swept_yet(state):
    # phase 6's claim window covers expires_tick == tick; sweep only after
    working = copy.deepcopy(state)
    working["regions"]["arm-1-b"]["loot"]["expires_tick"] = 1
    delta = resolve_yield(working, [], CONFIG, SEED)
    assert delta["loot_changes"] == {}


def test_moves_are_not_phase7_business(state):
    batch = {
        "actor": "force-1", "tick": 1, "origin": "agent",
        "orders": [{"action": "recruit", "region": "capital-1", "count": 9}],
    }
    assert resolve_yield(state, [batch], CONFIG, SEED) == resolve_yield(state, [], CONFIG, SEED)
