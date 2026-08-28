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


def _non_guild(quests_spawned):
    # guild quests (travel, hold) spawn every tick regardless of everything
    # else (F9) - most of these tests are specifically about vengeance/
    # rubber band behavior, so filter the standing guild pool out first
    return {qid: q for qid, q in quests_spawned.items() if q["type"] not in ("travel", "hold")}


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
    # 5/5/2 split: no strict unique leader - the guild still spawns its
    # standing travel quests regardless, since it isn't leader-dependent
    working = _quiet(state)
    for rid in ("ring-1", "ring-3"):
        working["regions"][rid]["owner"] = "force-1"
    delta = resolve_quest_spawn(working, [], CONFIG, SEED)
    assert _non_guild(delta["quests_spawned"]) == {}
    assert {q["type"] for q in delta["quests_spawned"].values()} == {"travel", "hold"}


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
    assert _non_guild(delta["quests_spawned"]) == {}  # vengeance also respects the cap


def test_killerless_death_spawns_no_vengeance(state):
    working = copy.deepcopy(state)
    working["adventurer_deaths_this_tick"] = [
        {"id": "adventurer-sago", "region": "ring-2", "killer": None}
    ]
    delta = resolve_quest_spawn(working, [], CONFIG, SEED)
    targets = {q["params"]["force"] for q in _non_guild(delta["quests_spawned"]).values()}
    assert targets == {"force-2"}  # only rubber-band quests, all at the leader


def test_guild_spawns_exactly_one_travel_quest_per_force(state):
    delta = resolve_quest_spawn(state, [], CONFIG, SEED)
    travels = [q for q in delta["quests_spawned"].values() if q["type"] == "travel"]
    assert sorted(q["params"]["force"] for q in travels) == ["force-1", "force-2", "force-3"]


def test_guild_travel_target_never_the_boards_own_capital(state):
    delta = resolve_quest_spawn(state, [], CONFIG, SEED)
    for quest in delta["quests_spawned"].values():
        if quest["type"] != "travel":
            continue
        force_id = quest["params"]["force"]
        capital_id = f"capital-{force_id.split('-', 1)[1]}"
        assert quest["params"]["region"] != capital_id


def test_guild_skips_a_force_that_already_has_an_active_travel_quest(state):
    working = copy.deepcopy(state)
    working["quests"]["active"]["travel-0-1"] = {
        "id": "travel-0-1", "type": "travel", "tier": "minor", "eligibility": "adventurer",
        "reward": 1, "stake": 1, "deadline": 5, "max_claimants": 1,
        "claimed_by": [], "progress": {}, "params": {"region": "ring-1", "force": "force-1"},
    }
    delta = resolve_quest_spawn(working, [], CONFIG, SEED)
    travels = [q for q in delta["quests_spawned"].values() if q["type"] == "travel"]
    assert sorted(q["params"]["force"] for q in travels) == ["force-2", "force-3"]


def test_guild_spawns_exactly_one_hold_quest_per_force(state):
    delta = resolve_quest_spawn(state, [], CONFIG, SEED)
    holds = [q for q in delta["quests_spawned"].values() if q["type"] == "hold"]
    assert sorted(q["params"]["force"] for q in holds) == ["force-1", "force-2", "force-3"]
    for quest in holds:
        assert quest["params"]["n_ticks"] == CONFIG.guild.bronze.hold_n_ticks
        assert quest["deadline"] == state["tick"] + 1 + CONFIG.quests.window_ticks


def test_guild_hold_target_never_the_boards_own_capital(state):
    delta = resolve_quest_spawn(state, [], CONFIG, SEED)
    for quest in delta["quests_spawned"].values():
        if quest["type"] != "hold":
            continue
        force_id = quest["params"]["force"]
        capital_id = f"capital-{force_id.split('-', 1)[1]}"
        assert quest["params"]["region"] != capital_id


def test_guild_hold_and_travel_targets_are_independent(state):
    # both use seeded picks over the same candidate pool, but with
    # deliberately different hash inputs - they need not (and, for at
    # least one force here, don't) land on the same region
    delta = resolve_quest_spawn(state, [], CONFIG, SEED)
    by_type_and_force = {
        (q["type"], q["params"]["force"]): q["params"]["region"]
        for q in delta["quests_spawned"].values() if q["type"] in ("travel", "hold")
    }
    assert any(
        by_type_and_force[("travel", f)] != by_type_and_force[("hold", f)]
        for f in ("force-1", "force-2", "force-3")
    )


def test_guild_skips_a_force_that_already_has_an_active_hold_quest(state):
    working = copy.deepcopy(state)
    working["quests"]["active"]["hold-0-1"] = {
        "id": "hold-0-1", "type": "hold", "tier": "minor", "eligibility": "adventurer",
        "reward": 1, "stake": 1, "deadline": 5, "max_claimants": 1,
        "claimed_by": [], "progress": {},
        "params": {"region": "ring-1", "force": "force-1", "n_ticks": 2},
    }
    delta = resolve_quest_spawn(working, [], CONFIG, SEED)
    holds = [q for q in delta["quests_spawned"].values() if q["type"] == "hold"]
    assert sorted(q["params"]["force"] for q in holds) == ["force-2", "force-3"]
    # force-1's travel quest is untouched by its hold quest already existing
    travels = [q for q in delta["quests_spawned"].values() if q["type"] == "travel"]
    assert sorted(q["params"]["force"] for q in travels) == ["force-1", "force-2", "force-3"]


def test_guild_travel_quests_never_count_against_the_rubber_bands_minor_cap(state):
    # force-2 is the strict leader here and would normally get both raid
    # and blockade minors (no vengeance this time, so both slots are free
    # for the rubber band); pre-filling the minor cap with guild quests
    # alone must not suppress them
    working = _quiet(state)
    working["regions"]["arm-3-b"]["owner"] = None  # a real blockade candidate exists
    working["regions"]["arm-3-b"]["units"] = 0
    for i, force_id in enumerate(("force-1", "force-2", "force-3"), start=1):
        working["quests"]["active"][f"travel-0-{i}"] = {
            "id": f"travel-0-{i}", "type": "travel", "tier": "minor",
            "eligibility": "adventurer", "reward": 1, "stake": 1, "deadline": 5,
            "max_claimants": 1, "claimed_by": [], "progress": {},
            "params": {"region": "ring-1", "force": force_id},
        }
    delta = resolve_quest_spawn(working, [], CONFIG, SEED)
    types = {q["type"] for q in _non_guild(delta["quests_spawned"]).values()}
    assert "raid" in types
    assert "blockade" in types


def test_moves_are_not_phase9_business(state):
    batch = {"actor": "force-1", "tick": 1, "origin": "agent",
             "orders": [{"action": "fortify", "region": "capital-1"}]}
    assert resolve_quest_spawn(state, [batch], CONFIG, SEED) == resolve_quest_spawn(state, [], CONFIG, SEED)
