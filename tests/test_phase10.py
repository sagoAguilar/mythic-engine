import copy
from pathlib import Path

import pytest
import yaml

from engine.config import load_era_config
from engine.phase10_supremacy import resolve_supremacy
from engine.validate import validate_world

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "tick_supremacia"
CONFIG = load_era_config(REPO_ROOT / "world" / "era.yml")
SEED = CONFIG.era.seed


def _load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.fixture()
def state():
    return _load(FIXTURE / "world.yml")


def test_fixture_world_is_schema_valid(state):
    validate_world(state)


def test_phase10_matches_expected_delta(state):
    expected = _load(FIXTURE / "expected_delta.yml")
    assert resolve_supremacy(state, [], CONFIG, SEED) == expected


def test_phase10_is_pure(state):
    snapshot = copy.deepcopy(state)
    first = resolve_supremacy(state, [], CONFIG, SEED)
    assert state == snapshot
    assert resolve_supremacy(state, [], CONFIG, SEED) == first


def test_applied_delta_keeps_world_schema_valid(state):
    delta = resolve_supremacy(state, [], CONFIG, SEED)
    world = copy.deepcopy(state)
    world["supremacy"] = delta["supremacy"]
    validate_world(world)  # the arbiter is caged too


def test_coronation_fires_at_k_ticks(state):
    working = copy.deepcopy(state)
    working["supremacy"]["streaks"]["force-2"] = CONFIG.coronation.k_ticks - 1
    delta = resolve_supremacy(working, [], CONFIG, SEED)
    assert delta["supremacy"]["streaks"]["force-2"] == CONFIG.coronation.k_ticks
    assert delta["coronation"] == "force-2"
    assert delta["era_ends"] == "coronation"


def test_supremacy_lost_resets_instead_of_coronating(state):
    working = copy.deepcopy(state)
    working["supremacy"]["streaks"]["force-2"] = CONFIG.coronation.k_ticks - 1
    working["regions"]["ring-3"]["owner"] = "force-3"  # down to 5/12
    delta = resolve_supremacy(working, [], CONFIG, SEED)
    assert delta["supremacy"]["streaks"]["force-2"] == 0
    assert delta["coronation"] is None
    assert delta["era_ends"] is None


def test_tick_cap_ends_the_era_without_coronation(state):
    working = copy.deepcopy(state)
    working["tick"] = CONFIG.era.tick_cap - 1  # resolving tick == cap
    delta = resolve_supremacy(working, [], CONFIG, SEED)
    assert delta["coronation"] is None
    assert delta["era_ends"] == "tick_cap"


def test_coronation_takes_precedence_over_tick_cap(state):
    working = copy.deepcopy(state)
    working["tick"] = CONFIG.era.tick_cap - 1
    working["supremacy"]["streaks"]["force-2"] = CONFIG.coronation.k_ticks - 1
    delta = resolve_supremacy(working, [], CONFIG, SEED)
    assert delta["era_ends"] == "coronation"


def _split_6_6(state):
    working = copy.deepcopy(state)
    for rid, region in working["regions"].items():
        region["owner"] = None
    for rid in ("capital-1", "arm-1-a", "arm-1-b", "ring-1", "arm-3-a", "arm-3-b"):
        working["regions"][rid]["owner"] = "force-1"
    for rid in ("capital-2", "arm-2-a", "arm-2-b", "ring-2", "ring-3", "capital-3"):
        working["regions"][rid]["owner"] = "force-2"
    return working


def test_two_forces_can_be_supreme_simultaneously(state):
    working = _split_6_6(state)
    working["supremacy"]["streaks"] = {"force-1": 3, "force-2": 3, "force-3": 0}
    delta = resolve_supremacy(working, [], CONFIG, SEED)
    assert delta["supremacy"]["streaks"] == {"force-1": 4, "force-2": 4, "force-3": 0}
    assert delta["supremacy"]["leader"] is None  # tie: no strict leader


def test_simultaneous_coronation_resolved_by_seed(state):
    working = _split_6_6(state)
    k = CONFIG.coronation.k_ticks
    working["supremacy"]["streaks"] = {"force-1": k - 1, "force-2": k - 1, "force-3": 0}
    delta = resolve_supremacy(working, [], CONFIG, SEED)
    assert delta["coronation"] in ("force-1", "force-2")
    assert delta["era_ends"] == "coronation"
    assert resolve_supremacy(working, [], CONFIG, SEED) == delta  # deterministic


def test_moves_are_not_phase10_business(state):
    batch = {"actor": "force-1", "tick": 5, "origin": "agent",
             "orders": [{"action": "fortify", "region": "capital-1"}]}
    assert resolve_supremacy(state, [batch], CONFIG, SEED) == resolve_supremacy(state, [], CONFIG, SEED)
