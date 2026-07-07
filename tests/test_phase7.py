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
    assert delta["essence_changes"]["force-1"] == 2 + 7 + 2


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
