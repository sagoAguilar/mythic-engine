import copy
from pathlib import Path

import pytest
import yaml

from engine.config import load_era_config
from engine.phase8_quests import resolve_quests
from engine.validate import validate_world

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "tick_quest_resueltas"
GUILD_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "tick_gremio_resuelto"
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


# --- guild boards: travel/hold verification + guild economics (point 9) ------


@pytest.fixture()
def guild_state():
    return _load(GUILD_FIXTURE / "world.yml")


def test_guild_fixture_world_is_schema_valid(guild_state):
    validate_world(guild_state)


def test_guild_phase8_matches_expected_delta(guild_state):
    expected = _load(GUILD_FIXTURE / "expected_delta.yml")
    assert resolve_quests(guild_state, [], CONFIG, SEED) == expected


def test_guild_phase8_is_pure(guild_state):
    snapshot = copy.deepcopy(guild_state)
    first = resolve_quests(guild_state, [], CONFIG, SEED)
    assert guild_state == snapshot
    assert resolve_quests(guild_state, [], CONFIG, SEED) == first


def test_guild_applied_delta_keeps_world_schema_valid(guild_state):
    delta = resolve_quests(guild_state, [], CONFIG, SEED)
    world = copy.deepcopy(guild_state)
    for actor, change in delta["essence_changes"].items():
        world["adventurers"][actor]["essence"] += change
    for adventurer_id, by_force in delta["reputation_changes"].items():
        for force_id, change in by_force.items():
            world["adventurers"][adventurer_id]["reputation"][force_id] += change
    for quest_id, progress in delta["quest_progress"].items():
        world["quests"]["active"][quest_id]["progress"] = progress
    for quest_id, status in delta["quests_resolved"].items():
        quest = world["quests"]["active"].pop(quest_id)
        quest["status"] = status
        quest["resolved_tick"] = world["tick"] + 1
        world["quests"]["resolved"][quest_id] = quest
    for adventurer_id, capabilities in delta["capability_grants"].items():
        held = world["adventurers"][adventurer_id].setdefault("capabilities", [])
        for capability in capabilities:
            if capability not in held:
                held.append(capability)
    for adventurer_id, by_force in delta["guild_completions"].items():
        guild = world["adventurers"][adventurer_id].setdefault("guild", {})
        for force_id, tiers in by_force.items():
            completed = guild.setdefault(force_id, {"completed": []})["completed"]
            for tier in tiers:
                if tier not in completed:
                    completed.append(tier)
    validate_world(world)  # the arbiter is caged too


def test_travel_fulfills_only_when_on_the_target_region(guild_state):
    working = copy.deepcopy(guild_state)
    working["adventurers"]["adventurer-sago"]["position"] = "capital-1"  # off ring-2
    delta = resolve_quests(working, [], CONFIG, SEED)
    # every ring-2 travel now waits; only the deadline-0 gold travel expires
    assert delta["quests_resolved"] == {"travel-0-2": "failure"}


def test_hold_streak_advances_without_completing(guild_state):
    delta = resolve_quests(guild_state, [], CONFIG, SEED)
    # hold-0-6 needs 2 consecutive ticks; standing here is tick 1 of 2
    assert delta["quest_progress"] == {"hold-0-6": {"adventurer-sago": 1}}
    assert "hold-0-6" not in delta["quests_resolved"]


def test_guild_success_pays_the_board_force_only_no_rivals(guild_state):
    delta = resolve_quests(guild_state, [], CONFIG, SEED)
    # the Silver travel-0-1 (force-1) grants +1 with force-1 and nothing to
    # rivals; contrast with damage quests, which hit every force.
    assert delta["reputation_changes"] == {
        "adventurer-sago": {"force-1": 1, "force-2": 5, "force-3": 1}
    }


def test_bronze_coin_flip_hit_and_miss(guild_state):
    delta = resolve_quests(guild_state, [], CONFIG, SEED)
    # travel-0-9 (force-3) is an even -> hit: +1 essence, +1 reputation.
    # travel-0-7 (force-2) is an odd -> miss: +2 essence, +0 reputation.
    assert delta["reputation_changes"]["adventurer-sago"]["force-3"] == 1
    # force-2's +5 comes entirely from the Gold hold; the Bronze miss adds none
    assert delta["reputation_changes"]["adventurer-sago"]["force-2"] == 5


def test_failed_guild_board_levies_no_reputation_penalty(guild_state):
    working = copy.deepcopy(guild_state)
    # expire everything; the adventurer keeps essence so nobody dies
    for quest in working["quests"]["active"].values():
        quest["deadline"] = 0
    delta = resolve_quests(working, [], CONFIG, SEED)
    assert all(s == "failure" for s in delta["quests_resolved"].values())
    assert delta["reputation_changes"] == {}
    assert delta["essence_changes"] == {}
    assert delta["adventurer_deaths"] == []


def test_guild_failure_can_still_kill_a_broke_adventurer(guild_state):
    working = copy.deepcopy(guild_state)
    working["adventurers"]["adventurer-sago"]["essence"] = 0
    # a single expired, unfulfillable guild board (target capital-3, deadline 0)
    working["quests"]["active"] = {
        "travel-0-2": working["quests"]["active"]["travel-0-2"]
    }
    delta = resolve_quests(working, [], CONFIG, SEED)
    assert delta["adventurer_deaths"] == [
        {"id": "adventurer-sago", "region": "ring-2", "killer": None}
    ]
    assert len(delta["graveyard_additions"]) == 1


# --- guild capability acquisition + completed-tier tracking (point 9) ---------


def test_completing_a_tier_records_it_and_confers_its_capability(guild_state):
    delta = resolve_quests(guild_state, [], CONFIG, SEED)
    # shared bronze->swift_march, shared silver->sanctuary, gold force-2->entrench;
    # the failed force-1 gold (travel-0-2) records nothing.
    assert delta["capability_grants"] == {
        "adventurer-sago": ["entrench", "sanctuary", "swift_march"]
    }
    assert delta["guild_completions"] == {
        "adventurer-sago": {
            "force-1": ["silver"],
            "force-2": ["bronze", "gold"],
            "force-3": ["bronze"],
        }
    }


def test_a_bronze_miss_still_completes_the_tier(guild_state):
    working = copy.deepcopy(guild_state)
    # keep only the Bronze miss (travel-0-7, force-2, odd coin -> miss)
    working["quests"]["active"] = {
        "travel-0-7": working["quests"]["active"]["travel-0-7"]
    }
    delta = resolve_quests(working, [], CONFIG, SEED)
    # a miss pays no reputation but still completes the tier and grants the cap
    assert delta["reputation_changes"] == {}
    assert delta["guild_completions"] == {"adventurer-sago": {"force-2": ["bronze"]}}
    assert delta["capability_grants"] == {"adventurer-sago": ["swift_march"]}


def test_gold_confers_the_board_forces_signature(guild_state):
    working = copy.deepcopy(guild_state)
    # keep only the Gold hold for force-2; entrench is force-2's signature
    working["quests"]["active"] = {
        "hold-0-5": working["quests"]["active"]["hold-0-5"]
    }
    delta = resolve_quests(working, [], CONFIG, SEED)
    assert delta["capability_grants"] == {"adventurer-sago": ["entrench"]}
    assert delta["guild_completions"] == {"adventurer-sago": {"force-2": ["gold"]}}


def test_platinum_records_the_tier_but_grants_no_capability(guild_state):
    working = copy.deepcopy(guild_state)
    # relabel the Silver force-1 travel as a Platinum board; v1 grants nothing
    quest = copy.deepcopy(working["quests"]["active"]["travel-0-1"])
    quest["params"]["guild_tier"] = "platinum"
    working["quests"]["active"] = {"travel-0-1": quest}
    delta = resolve_quests(working, [], CONFIG, SEED)
    assert delta["capability_grants"] == {}
    assert delta["guild_completions"] == {"adventurer-sago": {"force-1": ["platinum"]}}


def test_capabilities_already_held_are_not_regranted(guild_state):
    working = copy.deepcopy(guild_state)
    working["adventurers"]["adventurer-sago"]["capabilities"] = ["swift_march"]
    delta = resolve_quests(working, [], CONFIG, SEED)
    # swift_march is held; only the new caps appear, but the tier still records
    assert delta["capability_grants"] == {
        "adventurer-sago": ["entrench", "sanctuary"]
    }
    assert delta["guild_completions"]["adventurer-sago"]["force-3"] == ["bronze"]


def test_tiers_already_completed_are_not_rerecorded(guild_state):
    working = copy.deepcopy(guild_state)
    working["adventurers"]["adventurer-sago"]["guild"] = {
        "force-2": {"completed": ["bronze"]}
    }
    delta = resolve_quests(working, [], CONFIG, SEED)
    # force-2 bronze already stood; only the fresh gold is recorded for it
    assert delta["guild_completions"]["adventurer-sago"]["force-2"] == ["gold"]
    # its capability (swift_march) is still conferred if unheld
    assert "swift_march" in delta["capability_grants"]["adventurer-sago"]


def test_damage_quests_confer_no_guild_state(state, moves):
    delta = resolve_quests(state, moves, CONFIG, SEED)
    assert delta["capability_grants"] == {}
    assert delta["guild_completions"] == {}


# --- guild markers: insure / entrench / wager (paso 0) ------------------------

MARKERS_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "tick_gremio_marcadores"


@pytest.fixture()
def markers_state():
    return _load(MARKERS_FIXTURE / "world.yml")


@pytest.fixture()
def markers_moves():
    return [_load(p) for p in sorted((MARKERS_FIXTURE / "moves").glob("*.yml"))]


def test_markers_fixture_world_is_schema_valid(markers_state):
    validate_world(markers_state)


def test_markers_phase8_matches_expected_delta(markers_state, markers_moves):
    expected = _load(MARKERS_FIXTURE / "expected_delta.yml")
    assert resolve_quests(markers_state, markers_moves, CONFIG, SEED) == expected


def test_markers_phase8_is_pure(markers_state, markers_moves):
    state_snapshot = copy.deepcopy(markers_state)
    moves_snapshot = copy.deepcopy(markers_moves)
    first = resolve_quests(markers_state, markers_moves, CONFIG, SEED)
    assert markers_state == state_snapshot
    assert markers_moves == moves_snapshot
    assert resolve_quests(markers_state, markers_moves, CONFIG, SEED) == first


def test_markers_applied_delta_keeps_world_schema_valid(markers_state, markers_moves):
    delta = resolve_quests(markers_state, markers_moves, CONFIG, SEED)
    world = copy.deepcopy(markers_state)
    for actor, change in delta["essence_changes"].items():
        world["adventurers"][actor]["essence"] += change
    for adventurer_id, by_force in delta["reputation_changes"].items():
        for force_id, change in by_force.items():
            world["adventurers"][adventurer_id]["reputation"][force_id] += change
    for quest_id, markers in delta["quest_markers"].items():
        if quest_id in world["quests"]["active"]:
            world["quests"]["active"][quest_id]["params"].update(markers)
    for quest_id, status in delta["quests_resolved"].items():
        quest = world["quests"]["active"].pop(quest_id)
        quest["status"] = status
        quest["resolved_tick"] = world["tick"] + 1
        world["quests"]["resolved"][quest_id] = quest
    for adventurer_id, capabilities in delta["capability_grants"].items():
        held = world["adventurers"][adventurer_id].setdefault("capabilities", [])
        for capability in capabilities:
            if capability not in held:
                held.append(capability)
    for adventurer_id, by_force in delta["guild_completions"].items():
        guild = world["adventurers"][adventurer_id].setdefault("guild", {})
        for force_id, tiers in by_force.items():
            completed = guild.setdefault(force_id, {"completed": []})["completed"]
            for tier in tiers:
                if tier not in completed:
                    completed.append(tier)
    validate_world(world)  # the arbiter is caged too


def test_entrench_is_the_decisive_tick_on_a_hold(markers_state):
    working = copy.deepcopy(markers_state)
    working["quests"]["active"] = {
        "hold-1-a": working["quests"]["active"]["hold-1-a"]
    }
    entrench = {"actor": "adventurer-sago", "tick": 1, "origin": "agent",
               "orders": [{"action": "entrench", "quest_id": "hold-1-a"}]}
    # without entrench: streak 1 of 2, still active
    idle = resolve_quests(working, [], CONFIG, SEED)
    assert idle["quests_resolved"] == {}
    assert idle["quest_progress"] == {"hold-1-a": {"adventurer-sago": 1}}
    # with entrench: +1 progress tips it to 2 of 2 this same tick
    done = resolve_quests(working, [entrench], CONFIG, SEED)
    assert done["quests_resolved"] == {"hold-1-a": "success"}
    assert done["quest_markers"] == {"hold-1-a": {"entrenched": True}}
    assert done["essence_changes"]["adventurer-sago"] == 1  # +3 reward -2 cost


def test_wager_doubles_essence_only_not_reputation(markers_state):
    working = copy.deepcopy(markers_state)
    working["quests"]["active"] = {
        "travel-1-b": working["quests"]["active"]["travel-1-b"]  # Gold force-2
    }
    wager = {"actor": "adventurer-sago", "tick": 1, "origin": "agent",
             "orders": [{"action": "wager", "quest_id": "travel-1-b"}]}
    plain = resolve_quests(working, [], CONFIG, SEED)
    bet = resolve_quests(working, [wager], CONFIG, SEED)
    assert plain["essence_changes"]["adventurer-sago"] == 8   # flat gold
    assert bet["essence_changes"]["adventurer-sago"] == 16    # doubled
    # reputation is identical: wager never touches it
    assert plain["reputation_changes"] == bet["reputation_changes"]


def test_wagered_bronze_miss_forfeits_the_consolation(markers_state):
    working = copy.deepcopy(markers_state)
    # travel-1-e is a seeded MISS for this adventurer; a plain miss pays the
    # doubled consolation (2), a wagered miss pays nothing.
    quest = copy.deepcopy(working["quests"]["active"]["travel-1-f"])
    quest["id"] = "travel-1-e"
    quest["params"]["force"] = "force-3"
    working["quests"]["active"] = {"travel-1-e": quest}
    plain = resolve_quests(working, [], CONFIG, SEED)
    assert plain["essence_changes"]["adventurer-sago"] == 2   # bronze_miss
    wager = {"actor": "adventurer-sago", "tick": 1, "origin": "agent",
             "orders": [{"action": "wager", "quest_id": "travel-1-e"}]}
    bet = resolve_quests(working, [wager], CONFIG, SEED)
    assert bet["essence_changes"].get("adventurer-sago", 0) == 0  # nada
    # a miss still completes the tier and confers the capability
    assert bet["guild_completions"] == {"adventurer-sago": {"force-3": ["bronze"]}}


def test_insure_refunds_the_stake_and_can_avert_death(markers_state):
    working = copy.deepcopy(markers_state)
    working["adventurers"]["adventurer-sago"]["essence"] = 0
    # a single already-insured board that expires this tick (deadline 0)
    quest = copy.deepcopy(working["quests"]["active"]["travel-1-c"])
    quest["params"]["insured"] = True
    working["quests"]["active"] = {"travel-1-c": quest}
    delta = resolve_quests(working, [], CONFIG, SEED)
    assert delta["quests_resolved"] == {"travel-1-c": "failure"}
    assert delta["essence_changes"]["adventurer-sago"] == 1  # stake refunded
    assert delta["adventurer_deaths"] == []                  # refund saved him
    # without insurance the same broke adventurer dies
    bare = copy.deepcopy(quest)
    bare["params"]["insured"] = False
    working["quests"]["active"] = {"travel-1-c": bare}
    lethal = resolve_quests(working, [], CONFIG, SEED)
    assert lethal["adventurer_deaths"] == [
        {"id": "adventurer-sago", "region": "ring-2", "killer": None}
    ]


def test_marker_invocations_are_validated(markers_state):
    working = copy.deepcopy(markers_state)
    # give a plain damage quest to try to insure, and strip the wager capability
    working["adventurers"]["adventurer-sago"]["capabilities"] = ["entrench", "insure"]
    working["quests"]["active"]["raid-9-9"] = {
        "claimed_by": ["adventurer-sago"], "deadline": 8, "eligibility": "adventurer",
        "id": "raid-9-9", "max_claimants": 1,
        "params": {"force": "force-2", "region": "capital-2"},
        "progress": {}, "reward": 6, "stake": 1, "tier": "minor", "type": "raid",
    }
    batch = {"actor": "adventurer-sago", "tick": 1, "origin": "agent", "orders": [
        {"action": "wager", "quest_id": "travel-1-b"},      # capability not unlocked
        {"action": "entrench", "quest_id": "travel-1-b"},   # not a hold
        {"action": "insure", "quest_id": "raid-9-9"},       # not a guild quest
        {"action": "insure", "quest_id": "hold-1-a"},       # valid
        {"action": "insure", "quest_id": "hold-1-a"},       # already insured
    ]}
    delta = resolve_quests(working, [batch], CONFIG, SEED)
    reasons = [r["reason"] for r in delta["rejected_orders"]]
    assert any("capability not unlocked" in r for r in reasons)
    assert any("is not a hold quest" in r for r in reasons)
    assert any("is not a guild quest" in r for r in reasons)
    assert any("already insured" in r for r in reasons)
    # exactly one insure landed, on hold-1-a
    assert delta["quest_markers"] == {"hold-1-a": {"insured": True}}


def test_marker_on_a_quest_not_claimed_is_rejected(markers_state):
    working = copy.deepcopy(markers_state)
    working["quests"]["active"]["hold-1-a"]["claimed_by"] = []
    batch = {"actor": "adventurer-sago", "tick": 1, "origin": "agent",
             "orders": [{"action": "entrench", "quest_id": "hold-1-a"}]}
    delta = resolve_quests(working, [batch], CONFIG, SEED)
    assert delta["quest_markers"] == {}
    assert "not a claimant" in delta["rejected_orders"][0]["reason"]
