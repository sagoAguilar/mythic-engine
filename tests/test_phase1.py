import copy
from pathlib import Path

import pytest
import yaml

from engine.config import load_era_config
from engine.phase1_validation import resolve_validation
from engine.validate import validate_move, validate_world

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "tick_npc_sustitucion"
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


def test_phase1_matches_expected_delta(state, moves):
    expected = _load(FIXTURE / "expected_delta.yml")
    assert resolve_validation(state, moves, CONFIG, SEED) == expected


def test_phase1_output_batches_are_schema_valid(state, moves):
    delta = resolve_validation(state, moves, CONFIG, SEED)
    for batch in delta["batches"]:
        validate_move(batch, CONFIG)  # the arbiter is caged too


def test_phase1_is_pure(state, moves):
    state_snapshot = copy.deepcopy(state)
    moves_snapshot = copy.deepcopy(moves)
    first = resolve_validation(state, moves, CONFIG, SEED)
    assert state == state_snapshot
    assert moves == moves_snapshot
    assert resolve_validation(state, moves, CONFIG, SEED) == first


def _batch_for(delta, actor):
    return next(b for b in delta["batches"] if b["actor"] == actor)


# --- NPC force policy steps not covered by the fixture ----------------------


def test_npc_force_step3_moves_half_toward_neutral(state):
    # force-1 absent, not attacked, essence below fortify cost -> step 3.
    # Own regions adjacent to a neutral: capital-1 (4 units, -> arm-1-b)
    # and ring-1 (3 units, -> arm-1-b / ring-3). Most units: capital-1.
    state = copy.deepcopy(state)
    state["combats_last_tick"] = []
    state["forces"]["force-1"]["essence"] = CONFIG.economy.fortify_cost - 1
    delta = resolve_validation(state, [], CONFIG, SEED)
    assert _batch_for(delta, "force-1")["orders"] == [
        {"action": "move_units", "from": "capital-1", "to": "arm-1-b", "count": 2}
    ]


def test_npc_force_step3_tiebreak_lowest_destination_then_origin(state):
    # capital-1 and ring-1 tie at 4 units; candidate pairs
    # (capital-1, arm-1-b), (ring-1, arm-1-b), (ring-1, ring-3):
    # lowest destination id arm-1-b, then lowest origin id capital-1.
    state = copy.deepcopy(state)
    state["combats_last_tick"] = []
    state["forces"]["force-1"]["essence"] = 0
    state["regions"]["ring-1"]["units"] = 4
    delta = resolve_validation(state, [], CONFIG, SEED)
    assert _batch_for(delta, "force-1")["orders"] == [
        {"action": "move_units", "from": "capital-1", "to": "arm-1-b", "count": 2}
    ]


def test_npc_force_zero_half_falls_to_noop(state):
    # strongest neutral-adjacent region has 1 unit: floor(1/2) = 0 -> no-op
    state = copy.deepcopy(state)
    state["combats_last_tick"] = []
    state["forces"]["force-1"]["essence"] = 0
    for rid in ("capital-1", "ring-1"):
        state["regions"][rid]["units"] = 1
    delta = resolve_validation(state, [], CONFIG, SEED)
    assert _batch_for(delta, "force-1")["orders"] == []


def test_npc_force_skips_fortify_when_capital_lost_or_capped(state):
    state = copy.deepcopy(state)
    state["combats_last_tick"] = []
    state["regions"]["capital-3"]["fortification"] = CONFIG.economy.fortify_cap
    delta = resolve_validation(state, [], CONFIG, SEED)
    # falls to step 3: arm-3-a/arm-3-b/capital-3 all touch ring-3? only
    # arm-3-a and arm-3-b are neutral-adjacent (ring-3); arm-3-a has 2 units
    assert _batch_for(delta, "force-3")["orders"] == [
        {"action": "move_units", "from": "arm-3-a", "to": "ring-3", "count": 1}
    ]


# --- NPC adventurer policy steps not covered by the fixture -----------------


def test_npc_adventurer_flees_combat_to_weakest_adjacent_neutral(state):
    state = copy.deepcopy(state)
    state["regions"]["ring-3"]["loot"] = None
    state["combats_last_tick"] = ["ring-3"]
    # every ring-3 adjacent is owned in the fixture; free arm-3-a so a
    # flight target exists (fewest units among adjacent neutrals, lowest id)
    state["regions"]["arm-3-a"]["owner"] = None
    state["regions"]["arm-3-a"]["units"] = 0
    delta = resolve_validation(state, [], CONFIG, SEED)
    assert _batch_for(delta, "adventurer-sago")["orders"] == [
        {"action": "move_units", "from": "ring-3", "to": "arm-3-a", "count": 1}
    ]


def test_npc_adventurer_noop_when_nothing_applies(state):
    state = copy.deepcopy(state)
    state["regions"]["ring-3"]["loot"] = None
    state["combats_last_tick"] = []
    delta = resolve_validation(state, [], CONFIG, SEED)
    assert _batch_for(delta, "adventurer-sago")["orders"] == []


# --- substitution triggers ---------------------------------------------------


def _valid_batch(actor="force-1", tick=1):
    return {
        "actor": actor,
        "tick": tick,
        "origin": "agent",
        "orders": [{"action": "fortify", "region": "capital-1"}],
    }


def test_wrong_tick_triggers_substitution(state):
    delta = resolve_validation(state, [_valid_batch(tick=7)], CONFIG, SEED)
    assert any(
        s["actor"] == "force-1" and "tick" in s["reason"]
        for s in delta["substitutions"]
    )
    assert _batch_for(delta, "force-1")["origin"] == "npc"


def test_duplicate_batches_trigger_substitution(state):
    delta = resolve_validation(state, [_valid_batch(), _valid_batch()], CONFIG, SEED)
    assert any(
        s["actor"] == "force-1" and s["reason"] == "duplicate batches"
        for s in delta["substitutions"]
    )
    assert _batch_for(delta, "force-1")["origin"] == "npc"


def test_cap_violation_triggers_substitution(state):
    batch = _valid_batch()
    batch["orders"] = batch["orders"] * (CONFIG.orders.cap_force + 1)
    delta = resolve_validation(state, [batch], CONFIG, SEED)
    assert any(s["actor"] == "force-1" for s in delta["substitutions"])


def test_unknown_actor_batch_is_ignored_not_substituted(state):
    delta = resolve_validation(state, [_valid_batch(actor="force-9")], CONFIG, SEED)
    assert delta["ignored_batches"] == [
        {"actor": "force-9", "reason": "unknown actor"}
    ]
    assert all(s["actor"] != "force-9" for s in delta["substitutions"])
    assert all(b["actor"] != "force-9" for b in delta["batches"])


def test_unparseable_batch_is_ignored(state):
    delta = resolve_validation(state, ["not a mapping"], CONFIG, SEED)
    assert delta["ignored_batches"] == [
        {"actor": None, "reason": "unparseable batch"}
    ]


def test_every_actor_gets_exactly_one_batch(state, moves):
    delta = resolve_validation(state, moves, CONFIG, SEED)
    actors = sorted(list(state["forces"]) + list(state["adventurers"]))
    assert [b["actor"] for b in delta["batches"]] == actors
