import copy
from pathlib import Path

import pytest
import yaml

from engine.config import load_era_config
from engine.phase3_recruit_fortify import resolve_recruit_fortify
from engine.validate import validate_world

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "tick_recluta_fortifica"
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


def test_phase3_matches_expected_delta(state, moves):
    expected = _load(FIXTURE / "expected_delta.yml")
    assert resolve_recruit_fortify(state, moves, CONFIG, SEED) == expected


def test_phase3_is_pure(state, moves):
    state_snapshot = copy.deepcopy(state)
    moves_snapshot = copy.deepcopy(moves)
    first = resolve_recruit_fortify(state, moves, CONFIG, SEED)
    assert state == state_snapshot
    assert moves == moves_snapshot
    assert resolve_recruit_fortify(state, moves, CONFIG, SEED) == first


def test_applied_delta_keeps_world_schema_valid(state, moves):
    delta = resolve_recruit_fortify(state, moves, CONFIG, SEED)
    world = copy.deepcopy(state)
    for force_id, change in delta["essence_changes"].items():
        world["forces"][force_id]["essence"] += change
    for region_id, change in delta["unit_changes"].items():
        world["regions"][region_id]["units"] += change
    for region_id, change in delta["fortification_changes"].items():
        world["regions"][region_id]["fortification"] += change
    validate_world(world)  # the arbiter is caged too


def test_essence_never_overdrawn(state, moves):
    delta = resolve_recruit_fortify(state, moves, CONFIG, SEED)
    for force_id, change in delta["essence_changes"].items():
        assert state["forces"][force_id]["essence"] + change >= 0


def _batch(actor, orders, origin="agent"):
    return {"actor": actor, "tick": 1, "origin": origin, "orders": orders}


def test_unknown_region_rejected(state):
    delta = resolve_recruit_fortify(
        state,
        [_batch("force-1", [{"action": "recruit", "region": "atlantis", "count": 1}])],
        CONFIG,
        SEED,
    )
    assert delta["essence_changes"] == {}
    assert "atlantis" in delta["rejected_orders"][0]["reason"]


def test_double_fortify_within_cap_both_land(state):
    # capital-1 starts at 0, cap 3: two fortifies in one batch both land
    delta = resolve_recruit_fortify(
        state,
        [_batch("force-1", [{"action": "fortify", "region": "capital-1"},
                            {"action": "fortify", "region": "capital-1"}])],
        CONFIG,
        SEED,
    )
    assert delta["fortification_changes"] == {"capital-1": 2}
    assert delta["essence_changes"] == {"force-1": -2 * CONFIG.economy.fortify_cost}
    assert delta["rejected_orders"] == []


def test_non_phase3_orders_are_not_phase3_business(state):
    delta = resolve_recruit_fortify(
        state,
        [_batch("force-1", [{"action": "move_units", "from": "capital-1",
                             "to": "arm-1-a", "count": 1}])],
        CONFIG,
        SEED,
    )
    assert delta == {
        "essence_changes": {},
        "unit_changes": {},
        "fortification_changes": {},
        "rejected_orders": [],
    }
