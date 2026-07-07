import copy
from pathlib import Path

import pytest
import yaml

from engine.config import load_era_config
from engine.phase8_quests import resolve_quests
from engine.validate import validate_world

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "tick_quest_resueltas"
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


def test_phase8_matches_expected_delta(state, moves):
    expected = _load(FIXTURE / "expected_delta.yml")
    assert resolve_quests(state, moves, CONFIG, SEED) == expected


def test_phase8_is_pure(state, moves):
    state_snapshot = copy.deepcopy(state)
    moves_snapshot = copy.deepcopy(moves)
    first = resolve_quests(state, moves, CONFIG, SEED)
    assert state == state_snapshot
    assert moves == moves_snapshot
    assert resolve_quests(state, moves, CONFIG, SEED) == first


def test_applied_delta_keeps_world_schema_valid(state, moves):
    delta = resolve_quests(state, moves, CONFIG, SEED)
    world = copy.deepcopy(state)
    for actor, change in delta["essence_changes"].items():
        pool = world["adventurers"] if actor.startswith("adventurer-") else world["forces"]
        pool[actor]["essence"] += change
    for adventurer_id, by_force in delta["reputation_changes"].items():
        for force_id, change in by_force.items():
            world["adventurers"][adventurer_id]["reputation"][force_id] += change
    for quest_id, progress in delta["quest_progress"].items():
        world["quests"]["active"][quest_id]["progress"] = progress
    for quest_id, claimants in delta["quest_claims"].items():
        world["quests"]["active"][quest_id]["claimed_by"] = claimants
    for quest_id, status in delta["quests_resolved"].items():
        quest = world["quests"]["active"].pop(quest_id)
        quest["status"] = status
        quest["resolved_tick"] = world["tick"] + 1
        world["quests"]["resolved"][quest_id] = quest
    for death in delta["adventurer_deaths"]:
        del world["adventurers"][death["id"]]
    world["graveyard"].extend(delta["graveyard_additions"])
    validate_world(world)  # the arbiter is caged too


def test_blockade_streak_resets_when_occupation_breaks(state, moves):
    working = copy.deepcopy(state)
    working["regions"]["ring-3"]["owner"] = None  # force-3 lost the ground
    delta = resolve_quests(working, moves, CONFIG, SEED)
    assert delta["quest_progress"] == {"blockade-4-2": {"force-3": 0}}


def test_blockade_fulfills_on_reaching_n_ticks(state, moves):
    working = copy.deepcopy(state)
    working["quests"]["active"]["blockade-4-2"]["progress"] = {"force-3": 2}
    delta = resolve_quests(working, moves, CONFIG, SEED)
    assert delta["quests_resolved"]["blockade-4-2"] == "success"
    # force-3 collects the reward; its dethrone acceptance still loses the
    # seeded collision to force-1, so no stake is charged to it
    assert delta["essence_changes"]["force-3"] == 5
    assert "blockade-4-2" not in delta["quest_progress"]


def test_dethrone_fulfills_when_streak_returns_to_zero(state, moves):
    working = copy.deepcopy(state)
    working["quests"]["active"]["dethrone-6-5"]["claimed_by"] = ["force-3"]
    working["supremacy"]["streaks"]["force-2"] = 0
    delta = resolve_quests(working, moves, CONFIG, SEED)
    assert delta["quests_resolved"]["dethrone-6-5"] == "success"
    assert delta["essence_changes"]["force-3"] == 15


def test_unclaimed_quests_never_fulfill_only_expire(state, moves):
    working = copy.deepcopy(state)
    working["quests"]["active"]["dethrone-6-5"]["claimed_by"] = []
    working["supremacy"]["streaks"]["force-2"] = 0  # condition true, nobody claimed
    working["quests"]["active"]["dethrone-6-5"]["deadline"] = 0  # and expired
    delta = resolve_quests(working, [], CONFIG, SEED)
    assert delta["quests_resolved"]["dethrone-6-5"] == "failure"


def test_deadline_tick_itself_still_fulfills(state):
    working = copy.deepcopy(state)
    working["quests"]["active"]["raid-5-1"]["deadline"] = 1  # resolving tick
    delta = resolve_quests(working, [], CONFIG, SEED)
    assert delta["quests_resolved"]["raid-5-1"] == "success"


def test_stake_unaffordable_rejects_acceptance(state):
    working = copy.deepcopy(state)
    working["forces"]["force-1"]["essence"] = 1  # dethrone stake is 2
    batch = {"actor": "force-1", "tick": 1, "origin": "agent",
             "orders": [{"action": "accept_quest", "quest_id": "dethrone-6-5"}]}
    delta = resolve_quests(working, [batch], CONFIG, SEED)
    assert delta["quest_claims"] == {}
    assert "stake" in delta["rejected_orders"][0]["reason"]


def test_reputation_clamped_to_era_scale(state, moves):
    working = copy.deepcopy(state)
    working["adventurers"]["adventurer-sago"]["reputation"]["force-1"] = -95
    delta = resolve_quests(working, moves, CONFIG, SEED)
    # -95 - 15 would cross scale_min -100; the delta must stop at the floor
    assert delta["reputation_changes"]["adventurer-sago"]["force-1"] == -5


def test_non_quest_orders_are_not_phase8_business(state):
    batch = {"actor": "force-1", "tick": 1, "origin": "agent",
             "orders": [{"action": "fortify", "region": "capital-1"}]}
    delta = resolve_quests(state, [batch], CONFIG, SEED)
    assert delta["rejected_orders"] == []
    assert delta["quest_claims"] == {}
