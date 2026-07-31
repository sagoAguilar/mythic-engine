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
    for actor, change in delta["essence_changes"].items():
        pool = world["adventurers"] if actor.startswith("adventurer-") else world["forces"]
        pool[actor]["essence"] += change
    for adventurer_id, by_force in delta["reputation_changes"].items():
        for force_id, change in by_force.items():
            world["adventurers"][adventurer_id]["reputation"][force_id] += change
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


def _trade(actor, region, tick=1, origin="human"):
    return {
        "actor": actor, "tick": tick, "origin": origin,
        "orders": [{"action": "trade", "region": region}],
    }


def test_trade_rejected_in_neutral_territory(state):
    # both adventurers start at ring-3, which is neutral (owner null)
    delta = resolve_claim_loot(state, [_trade("adventurer-sago", "ring-3")], CONFIG, SEED)
    assert delta["essence_changes"] == {}
    assert "not a force's territory" in delta["rejected_orders"][0]["reason"]


def test_trade_rejected_below_reputation_threshold(state):
    working = copy.deepcopy(state)
    working["adventurers"]["adventurer-sago"]["position"] = "ring-1"  # force-1's
    delta = resolve_claim_loot(working, [_trade("adventurer-sago", "ring-1")], CONFIG, SEED)
    assert delta["essence_changes"] == {}
    assert "below the trade threshold" in delta["rejected_orders"][0]["reason"]


def test_trade_rejected_when_essence_cannot_cover_the_cost(state):
    working = copy.deepcopy(state)
    working["adventurers"]["adventurer-sago"]["position"] = "ring-1"
    working["adventurers"]["adventurer-sago"]["reputation"]["force-1"] = 10
    working["adventurers"]["adventurer-sago"]["essence"] = 2  # trade_cost is 3
    delta = resolve_claim_loot(working, [_trade("adventurer-sago", "ring-1")], CONFIG, SEED)
    assert delta["essence_changes"] == {}
    assert "exceeds the 2 essence remaining" in delta["rejected_orders"][0]["reason"]


def test_trade_success_transfers_essence_and_raises_reputation(state):
    # sago @ ring-2 (force-2's, ring tier 50%): sha256(seed:1:adventurer-sago:
    # force-2) -> roll 40 < 50 -> success
    working = copy.deepcopy(state)
    working["adventurers"]["adventurer-sago"]["position"] = "ring-2"
    working["adventurers"]["adventurer-sago"]["reputation"]["force-2"] = 10
    delta = resolve_claim_loot(working, [_trade("adventurer-sago", "ring-2")], CONFIG, SEED)
    assert delta["rejected_orders"] == []
    assert delta["trade_results"] == [
        {"actor": "adventurer-sago", "force": "force-2", "success": True}
    ]
    assert delta["essence_changes"] == {"adventurer-sago": -3, "force-2": 3}
    assert delta["reputation_changes"] == {"adventurer-sago": {"force-2": 2}}


def test_trade_failure_moves_nothing_but_isnt_rejected(state):
    # sago @ ring-1 (force-1's, ring tier 50%): sha256(seed:1:adventurer-sago:
    # force-1) -> roll 90 >= 50 -> failure
    working = copy.deepcopy(state)
    working["adventurers"]["adventurer-sago"]["position"] = "ring-1"
    working["adventurers"]["adventurer-sago"]["reputation"]["force-1"] = 10
    delta = resolve_claim_loot(working, [_trade("adventurer-sago", "ring-1")], CONFIG, SEED)
    assert delta["rejected_orders"] == []  # a lost roll isn't a rejection
    assert delta["trade_results"] == [
        {"actor": "adventurer-sago", "force": "force-1", "success": False}
    ]
    assert delta["essence_changes"] == {}
    assert delta["reputation_changes"] == {}


def test_trade_arm_tier_uses_arms_own_success_percentage(state):
    # elder @ arm-1-a (force-1's, arm tier 75%): sha256(seed:1:adventurer-elder:
    # force-1) -> roll 29 < 75 -> success
    working = copy.deepcopy(state)
    working["adventurers"]["adventurer-elder"]["position"] = "arm-1-a"
    working["adventurers"]["adventurer-elder"]["reputation"]["force-1"] = 10
    delta = resolve_claim_loot(working, [_trade("adventurer-elder", "arm-1-a")], CONFIG, SEED)
    assert delta["trade_results"] == [
        {"actor": "adventurer-elder", "force": "force-1", "success": True}
    ]


def test_trade_capital_tier_always_succeeds(state):
    # elder @ capital-3 (force-3's, capital tier 100%): sha256(seed:1:
    # adventurer-elder:force-3) -> roll 90, which would fail ring/arm but
    # capital's 100% succeeds regardless
    working = copy.deepcopy(state)
    working["adventurers"]["adventurer-elder"]["position"] = "capital-3"
    working["adventurers"]["adventurer-elder"]["reputation"]["force-3"] = 10
    delta = resolve_claim_loot(working, [_trade("adventurer-elder", "capital-3")], CONFIG, SEED)
    assert delta["trade_results"] == [
        {"actor": "adventurer-elder", "force": "force-3", "success": True}
    ]


def test_trade_reputation_gain_clamps_to_the_eras_scale_max(state):
    working = copy.deepcopy(state)
    working["adventurers"]["adventurer-sago"]["position"] = "ring-2"
    working["adventurers"]["adventurer-sago"]["reputation"]["force-2"] = 99
    delta = resolve_claim_loot(working, [_trade("adventurer-sago", "ring-2")], CONFIG, SEED)
    assert delta["reputation_changes"] == {"adventurer-sago": {"force-2": 1}}  # 99 -> 100, not 101


def test_trade_by_force_rejected(state):
    delta = resolve_claim_loot(
        state, [_trade("force-1", "capital-1", origin="agent")], CONFIG, SEED,
    )
    assert "only an adventurer may trade" in delta["rejected_orders"][0]["reason"]


def test_non_claim_orders_are_not_phase6_business(state):
    batch = {
        "actor": "adventurer-sago", "tick": 1, "origin": "human",
        "orders": [{"action": "move_units", "from": "ring-3", "to": "ring-1", "count": 1}],
    }
    delta = resolve_claim_loot(state, [batch], CONFIG, SEED)
    assert delta == {
        "essence_changes": {}, "reputation_changes": {}, "loot_changes": {},
        "loot_claims": {}, "trade_results": [], "rejected_orders": [],
    }
