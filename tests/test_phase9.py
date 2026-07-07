import copy
from pathlib import Path

import pytest
import yaml

from engine.config import load_era_config
from engine.phase9_spawn import resolve_quest_spawn
from engine.validate import validate_world

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "tick_rubberband_spawn"
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
    working["adventurer_deaths_this_tick"] = _load(FIXTURE / "deaths_this_tick.yml")
    return working


def test_fixture_world_is_schema_valid(world):
    validate_world(world)


def test_phase9_matches_expected_delta(state):
    expected = _load(FIXTURE / "expected_delta.yml")
    assert resolve_quest_spawn(state, [], CONFIG, SEED) == expected


def test_phase9_is_pure(state):
    snapshot = copy.deepcopy(state)
    first = resolve_quest_spawn(state, [], CONFIG, SEED)
    assert state == snapshot
    assert resolve_quest_spawn(state, [], CONFIG, SEED) == first


def test_spawned_quests_are_schema_valid(state, world):
    delta = resolve_quest_spawn(state, [], CONFIG, SEED)
    result = copy.deepcopy(world)
    result["quests"]["active"].update(delta["quests_spawned"])
    validate_world(result)  # the arbiter is caged too


def _quiet(state):
    working = copy.deepcopy(state)
    working["adventurer_deaths_this_tick"] = []
    return working


def test_minor_band_without_major(state):
    # drop the leader to exactly 6/12 = 0.5: > 0.45, not > 0.55
    working = _quiet(state)
    working["regions"]["arm-1-b"]["owner"] = "force-1"
    delta = resolve_quest_spawn(working, [], CONFIG, SEED)
    tiers = {q["tier"] for q in delta["quests_spawned"].values()}
    assert tiers == {"minor"}


def test_blockade_spawns_when_slot_and_candidate_exist(state):
    # no vengeance; free a neutral adjacent to the leader's territory
    working = _quiet(state)
    working["regions"]["arm-3-b"]["owner"] = None
    working["regions"]["arm-3-b"]["units"] = 0
    delta = resolve_quest_spawn(working, [], CONFIG, SEED)
    blockades = [q for q in delta["quests_spawned"].values() if q["type"] == "blockade"]
    assert len(blockades) == 1
    assert blockades[0]["params"] == {
        "region": "arm-3-b",
        "n_ticks": CONFIG.quests.blockade_n_ticks,
        "force": "force-2",
    }


def test_dethrone_preferred_once_leader_has_a_streak(state):
    working = _quiet(state)
    working["supremacy"]["streaks"]["force-2"] = 2
    delta = resolve_quest_spawn(working, [], CONFIG, SEED)
    majors = [q for q in delta["quests_spawned"].values() if q["tier"] == "major"]
    assert len(majors) == 1
    assert majors[0]["type"] == "dethrone"
    assert majors[0]["params"] == {"force": "force-2"}


def test_tied_leadership_spawns_no_rubber_band(state):
    # 5/5/2 split: no strict unique leader
    working = _quiet(state)
    for rid in ("ring-1", "ring-3"):
        working["regions"][rid]["owner"] = "force-1"
    delta = resolve_quest_spawn(working, [], CONFIG, SEED)
    assert delta["quests_spawned"] == {}


def test_full_caps_spawn_nothing(state):
    working = copy.deepcopy(state)
    working["quests"]["active"] = {
        "raid-0-1": {"id": "raid-0-1", "type": "raid", "tier": "minor",
                     "eligibility": "any", "reward": 6, "stake": 1, "deadline": 9,
                     "max_claimants": "open", "claimed_by": [], "progress": {},
                     "params": {"region": "arm-1-a", "force": "force-1"}},
        "blockade-0-2": {"id": "blockade-0-2", "type": "blockade", "tier": "minor",
                         "eligibility": "any", "reward": 5, "stake": 1, "deadline": 9,
                         "max_claimants": "open", "claimed_by": [], "progress": {},
                         "params": {"region": "ring-3", "n_ticks": 3, "force": "force-2"}},
        "attrition-0-3": {"id": "attrition-0-3", "type": "attrition", "tier": "major",
                          "eligibility": "forces", "reward": 10, "stake": 2, "deadline": 9,
                          "max_claimants": 1, "claimed_by": [], "progress": {},
                          "params": {"force": "force-2", "units_at_spawn": 12, "delta": 4}},
    }
    delta = resolve_quest_spawn(working, [], CONFIG, SEED)
    assert delta["quests_spawned"] == {}  # vengeance also respects the cap


def test_killerless_death_spawns_no_vengeance(state):
    working = copy.deepcopy(state)
    working["adventurer_deaths_this_tick"] = [
        {"id": "adventurer-sago", "region": "ring-2", "killer": None}
    ]
    delta = resolve_quest_spawn(working, [], CONFIG, SEED)
    targets = {q["params"]["force"] for q in delta["quests_spawned"].values()}
    assert targets == {"force-2"}  # only rubber-band quests, all at the leader


def test_moves_are_not_phase9_business(state):
    batch = {"actor": "force-1", "tick": 1, "origin": "agent",
             "orders": [{"action": "fortify", "region": "capital-1"}]}
    assert resolve_quest_spawn(state, [batch], CONFIG, SEED) == resolve_quest_spawn(state, [], CONFIG, SEED)
