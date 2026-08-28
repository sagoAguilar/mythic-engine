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
    # capital-1 starts at 0, cap 3: two fortifies in one batch both land -
    # escalating cost (level_1 then level_2), needs essence bumped since
    # the fixture's force-1 essence was sized for the old flat cost
    working = copy.deepcopy(state)
    working["forces"]["force-1"]["essence"] = 100
    delta = resolve_recruit_fortify(
        working,
        [_batch("force-1", [{"action": "fortify", "region": "capital-1"},
                            {"action": "fortify", "region": "capital-1"}])],
        CONFIG,
        SEED,
    )
    assert delta["fortification_changes"] == {"capital-1": 2}
    assert delta["essence_changes"] == {
        "force-1": -(CONFIG.economy.fortify_cost.level_1 + CONFIG.economy.fortify_cost.level_2)
    }
    assert delta["rejected_orders"] == []


def test_fortify_charges_the_current_levels_cost_not_a_flat_rate(state):
    # capital-2 starts at fortification 2 (see fixture) - advancing to 3
    # must charge level_3's cost, not level_1's, and not a flat rate
    working = copy.deepcopy(state)
    working["forces"]["force-2"]["essence"] = 100
    delta = resolve_recruit_fortify(
        working,
        [_batch("force-2", [{"action": "fortify", "region": "capital-2"}])],
        CONFIG,
        SEED,
    )
    assert delta["essence_changes"] == {"force-2": -CONFIG.economy.fortify_cost.level_3}


def _decree(kind, region, count):
    return {"action": "decree", "kind": kind, "region": region, "count": count}


def test_decree_dismiss_reduces_units_with_no_essence_change(state):
    delta = resolve_recruit_fortify(
        state, [_batch("force-1", [_decree("dismiss", "capital-1", 2)])], CONFIG, SEED,
    )
    assert delta["unit_changes"] == {"capital-1": -2}
    assert "force-1" not in delta["essence_changes"]
    assert delta["rejected_orders"] == []


def test_decree_dismiss_exceeding_available_units_rejected(state):
    delta = resolve_recruit_fortify(
        state, [_batch("force-1", [_decree("dismiss", "capital-1", 99)])], CONFIG, SEED,
    )
    assert delta["unit_changes"] == {}
    assert "exceeds" in delta["rejected_orders"][0]["reason"]


def test_decree_dismiss_sees_units_recruited_earlier_in_the_same_batch(state):
    # capital-1 starts at 4 units; +2 recruited, then -6 dismissed - only
    # legal if dismiss accounts for the recruit that landed just before it
    working = copy.deepcopy(state)
    working["forces"]["force-1"]["essence"] = 100
    delta = resolve_recruit_fortify(
        working,
        [_batch("force-1", [
            {"action": "recruit", "region": "capital-1", "count": 2},
            _decree("dismiss", "capital-1", 6),
        ])],
        CONFIG, SEED,
    )
    assert delta["unit_changes"] == {"capital-1": 2 - 6}
    assert delta["rejected_orders"] == []


def test_decree_surge_recruit_first_use_charges_tier_one_and_doubles_units(state):
    working = copy.deepcopy(state)
    delta = resolve_recruit_fortify(
        working, [_batch("force-1", [_decree("surge_recruit", "capital-1", 2)])], CONFIG, SEED,
    )
    surcharge = CONFIG.economy.decree_surge_surcharge.at_streak(1)
    assert delta["unit_changes"] == {"capital-1": 4}
    assert delta["essence_changes"] == {"force-1": -(2 * CONFIG.economy.recruit_cost + surcharge)}
    assert delta["surge_streak_changes"] == {"force-1": 1}


def test_decree_surge_recruit_charges_by_the_forces_prior_streak(state):
    working = copy.deepcopy(state)
    working["forces"]["force-1"]["essence"] = 100
    working["forces"]["force-1"]["surge_streak"] = 1  # already on a streak
    delta = resolve_recruit_fortify(
        working, [_batch("force-1", [_decree("surge_recruit", "capital-1", 1)])], CONFIG, SEED,
    )
    surcharge = CONFIG.economy.decree_surge_surcharge.at_streak(2)
    assert delta["essence_changes"] == {"force-1": -(CONFIG.economy.recruit_cost + surcharge)}
    assert delta["surge_streak_changes"] == {"force-1": 2}


def test_decree_surge_recruit_surcharge_caps_at_the_third_tier(state):
    working = copy.deepcopy(state)
    working["forces"]["force-1"]["essence"] = 100
    working["forces"]["force-1"]["surge_streak"] = 3  # already at the cap
    delta = resolve_recruit_fortify(
        working, [_batch("force-1", [_decree("surge_recruit", "capital-1", 1)])], CONFIG, SEED,
    )
    surcharge = CONFIG.economy.decree_surge_surcharge.at_streak(3)
    assert delta["essence_changes"] == {"force-1": -(CONFIG.economy.recruit_cost + surcharge)}
    assert delta["surge_streak_changes"] == {"force-1": 3}  # stays capped, doesn't grow past 3


def test_decree_surge_recruit_shares_one_streak_across_same_tick_orders(state):
    # two surge_recruit orders in the same batch: both charged the SAME
    # (first-use) surcharge - it doesn't escalate again within the tick
    working = copy.deepcopy(state)
    working["forces"]["force-1"]["essence"] = 100
    delta = resolve_recruit_fortify(
        working,
        [_batch("force-1", [
            _decree("surge_recruit", "capital-1", 1),
            _decree("surge_recruit", "arm-1-a", 1),
        ])],
        CONFIG, SEED,
    )
    surcharge = CONFIG.economy.decree_surge_surcharge.at_streak(1)
    per_order_cost = CONFIG.economy.recruit_cost + surcharge
    assert delta["essence_changes"] == {"force-1": -2 * per_order_cost}
    assert delta["surge_streak_changes"] == {"force-1": 1}


def test_decree_surge_recruit_insufficient_essence_rejected_and_streak_unchanged(state):
    # force-3 has essence 3; even the cheapest surge_recruit (2 + 5 = 7) fails
    delta = resolve_recruit_fortify(
        state, [_batch("force-3", [_decree("surge_recruit", "capital-3", 1)])], CONFIG, SEED,
    )
    assert delta["unit_changes"] == {}
    assert "force-3" not in delta["essence_changes"]
    assert "force-3" not in delta["surge_streak_changes"]  # was 0, stays 0 - nothing to report
    assert "exceeds" in delta["rejected_orders"][0]["reason"]


def test_decree_resets_streak_for_forces_that_did_not_use_it_this_tick(state):
    working = copy.deepcopy(state)
    working["forces"]["force-2"]["surge_streak"] = 2
    delta = resolve_recruit_fortify(working, [], CONFIG, SEED)
    assert delta["surge_streak_changes"] == {"force-2": 0}


def test_decree_by_adventurer_rejected(state):
    delta = resolve_recruit_fortify(
        state,
        [_batch("adventurer-sago", [_decree("dismiss", "capital-1", 1)], origin="human")],
        CONFIG, SEED,
    )
    assert "issue a decree" in delta["rejected_orders"][0]["reason"]


def test_decree_on_unowned_region_rejected(state):
    delta = resolve_recruit_fortify(
        state, [_batch("force-1", [_decree("dismiss", "capital-2", 1)])], CONFIG, SEED,
    )
    assert "not owned by force-1" in delta["rejected_orders"][0]["reason"]


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
        "surge_streak_changes": {},
        "rejected_orders": [],
    }
