import copy
from pathlib import Path

import pytest
import yaml

from engine.config import load_era_config
from engine.phase11_chronicle import resolve_chronicle
from engine.validate import validate_world

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "tick_cronica"
CONFIG = load_era_config(REPO_ROOT / "world" / "era.yml")
SEED = CONFIG.era.seed

SECTIONS = [
    "## Órdenes", "## Combates", "## Colisiones", "## Economía",
    "## Quests", "## Supremacía", "## Aventurero",
]


def _load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.fixture()
def world():
    return _load(FIXTURE / "world.yml")


@pytest.fixture()
def state(world):
    working = copy.deepcopy(world)
    working["tick_events"] = _load(FIXTURE / "tick_events.yml")
    return working


def test_fixture_world_is_schema_valid(world):
    validate_world(world)


def test_chronicle_matches_expected_bytes(state):
    expected = (FIXTURE / "expected_chronicle.md").read_text(encoding="utf-8")
    delta = resolve_chronicle(state, [], CONFIG, SEED)
    assert delta == {"chronicle": expected}


def test_phase11_is_pure(state):
    snapshot = copy.deepcopy(state)
    first = resolve_chronicle(state, [], CONFIG, SEED)
    assert state == snapshot
    assert resolve_chronicle(state, [], CONFIG, SEED) == first


def _empty_events():
    return {
        "batches": [], "substitutions": [], "rejected_orders": [],
        "pending_combats": [], "combats": [], "yields": {},
        "quests_spawned": {}, "quests_resolved": {},
        "adventurer_moves": {}, "loot_claims": {},
        "adventurer_spawned": [], "adventurer_deaths": [],
        "supremacy": {"supremacy": {"leader": None,
                                    "streaks": {"force-1": 0, "force-2": 0, "force-3": 0}},
                      "coronation": None, "era_ends": None},
    }


def test_quiet_tick_still_emits_every_section(state):
    working = copy.deepcopy(state)
    working["tick_events"] = _empty_events()
    working["adventurers"] = {}
    text = resolve_chronicle(working, [], CONFIG, SEED)["chronicle"]
    for section in SECTIONS:
        assert section in text
    assert "Sustituciones: -" in text
    assert "Coronación: -" in text
    assert "Fin de era: -" in text


def test_coronation_and_era_end_lines(state):
    working = copy.deepcopy(state)
    working["tick_events"]["supremacy"]["coronation"] = "force-2"
    working["tick_events"]["supremacy"]["era_ends"] = "coronation"
    text = resolve_chronicle(working, [], CONFIG, SEED)["chronicle"]
    assert "Coronación: force-2" in text
    assert "Fin de era: coronation" in text


def test_dead_adventurer_row(state):
    working = copy.deepcopy(state)
    del working["adventurers"]["adventurer-sago"]
    working["tick_events"]["adventurer_deaths"] = [
        {"id": "adventurer-sago", "region": "ring-2", "killer": "force-1"}
    ]
    working["tick_events"]["adventurer_moves"] = {}
    text = resolve_chronicle(working, [], CONFIG, SEED)["chronicle"]
    assert "| adventurer-sago | † ring-2 | - | - | muerte:force-1 |" in text


def test_noop_batch_renders_a_noop_row(state):
    working = copy.deepcopy(state)
    working["tick_events"]["batches"].append(
        {"actor": "adventurer-idle", "tick": 1, "origin": "npc", "orders": []}
    )
    text = resolve_chronicle(working, [], CONFIG, SEED)["chronicle"]
    assert "| adventurer-idle | npc | - | no-op | - | - |" in text


def test_loot_claim_and_spawn_events(state):
    working = copy.deepcopy(state)
    working["tick_events"]["adventurer_spawned"] = ["adventurer-sago"]
    working["tick_events"]["loot_claims"] = {"adventurer-sago": 3}
    text = resolve_chronicle(working, [], CONFIG, SEED)["chronicle"]
    assert "spawn; move:capital-2; botín:+3" in text


def test_moves_are_not_phase11_business(state):
    batch = {"actor": "force-1", "tick": 1, "origin": "agent",
             "orders": [{"action": "fortify", "region": "capital-1"}]}
    assert resolve_chronicle(state, [batch], CONFIG, SEED) == resolve_chronicle(state, [], CONFIG, SEED)
