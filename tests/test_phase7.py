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
    for region_id, change in delta["fortification_changes"].items():
        world["regions"][region_id]["fortification"] += change
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


def test_fortify_upkeep_paid_when_essence_covers_it(state):
    # capital-1 (force-1) fortified to level 1: upkeep 1, well within
    # force-1's yield/reserve - pays quietly, no erosion
    working = copy.deepcopy(state)
    working["regions"]["capital-1"]["fortification"] = 1
    delta = resolve_yield(working, [], CONFIG, SEED)
    assert delta["fortification_changes"] == {}
    # base delta (4, see test_phase7_matches_expected_delta) minus fortify_upkeep.at_level(1)=1
    assert delta["essence_changes"]["force-1"] == 4 - CONFIG.economy.fortify_upkeep.at_level(1)


def test_fortify_upkeep_erodes_when_essence_cannot_cover_it(state):
    # force-3 has no essence reserve and no yield this tick (all its
    # regions zeroed out); fortifying arm-3-a to level 1 means its
    # upkeep (1) can't be paid from a 0-essence balance -> erodes
    working = copy.deepcopy(state)
    working["forces"]["force-3"]["essence"] = 0
    for rid in ("capital-3", "arm-3-a", "ring-3"):
        working["regions"][rid]["yield"] = 0
    working["regions"]["arm-3-a"]["fortification"] = 1
    delta = resolve_yield(working, [], CONFIG, SEED)
    assert delta["fortification_changes"] == {"arm-3-a": -1}
    # the unpaid upkeep is not deducted - erosion replaces the charge
    assert delta["essence_changes"].get("force-3", 0) == 0


def test_fortify_upkeep_uses_the_forces_real_balance_not_just_tick_flow(state):
    # force-3 sits on a large essence reserve even though this tick's
    # flow alone (yield only, no unit upkeep here) would already cover
    # it - confirms the check is against the actual balance, not a
    # marginal flow that would coincidentally look insufficient
    working = copy.deepcopy(state)
    working["forces"]["force-3"]["essence"] = 1000
    working["regions"]["arm-3-a"]["fortification"] = 3  # upkeep 6
    delta = resolve_yield(working, [], CONFIG, SEED)
    assert delta["fortification_changes"] == {}
    assert delta["essence_changes"]["force-3"] == 5 - CONFIG.economy.fortify_upkeep.at_level(3)


def test_fortify_erosion_pays_cheapest_level_first(state):
    # force-1 holds two fortified regions: capital-1 at level 1 (upkeep 1)
    # and ring-1 at level 2 (upkeep 3). Yields zeroed so the only flow is
    # unit upkeep (6 units -> floor(6/5)=1); essence set to 3 so the
    # remaining pool (3 - 1 = 2) covers the cheaper level-1 upkeep but
    # not both - ring-1 (pricier) erodes, capital-1 (cheaper) is paid
    working = copy.deepcopy(state)
    working["forces"]["force-1"]["essence"] = 3
    for rid in ("capital-1", "ring-1", "arm-1-a"):
        working["regions"][rid]["yield"] = 0
    working["regions"]["capital-1"]["fortification"] = 1
    working["regions"]["ring-1"]["fortification"] = 2
    delta = resolve_yield(working, [], CONFIG, SEED)
    assert delta["fortification_changes"] == {"ring-1": -1}
    # base flow -1 (unit upkeep only) minus capital-1's paid upkeep (1)
    assert delta["essence_changes"]["force-1"] == -2


def test_fortify_erosion_tiebreaks_by_region_id_at_the_same_level(state):
    # force-1 holds two regions at the identical fortification level;
    # yields zeroed and essence trimmed so the remaining pool covers
    # exactly one of the two level-1 upkeeps (cost 1 each) - the
    # lexically smaller region id ("arm-1-a" < "arm-1-b") pays first,
    # the other erodes
    working = copy.deepcopy(state)
    working["forces"]["force-1"]["essence"] = 2
    for rid in ("capital-1", "ring-1", "arm-1-a"):
        working["regions"][rid]["yield"] = 0
    working["regions"]["arm-1-a"]["fortification"] = 1
    working["regions"]["arm-1-b"]["fortification"] = 1
    working["regions"]["arm-1-b"]["owner"] = "force-1"
    working["regions"]["arm-1-b"]["yield"] = 0
    delta = resolve_yield(working, [], CONFIG, SEED)
    # flow = 0 yield - 1 unit upkeep (6 units, floor(6/5)=1); remaining
    # pool = essence(2) - 1 = 1 - covers exactly one level-1 upkeep (1)
    assert delta["fortification_changes"] == {"arm-1-b": -1}


def test_moves_are_not_phase7_business(state):
    batch = {
        "actor": "force-1", "tick": 1, "origin": "agent",
        "orders": [{"action": "recruit", "region": "capital-1", "count": 9}],
    }
    assert resolve_yield(state, [batch], CONFIG, SEED) == resolve_yield(state, [], CONFIG, SEED)
