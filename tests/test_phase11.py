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
        "adventurer_moves": {}, "loot_claims": {}, "trade_results": [],
        "adventurer_spawned": [], "adventurer_deaths": [],
        "sanctuary_activated": [], "capability_grants": {},
        "guild_completions": {},
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


def _adventurer_events(text):
    """The eventos cell of the adventurer-sago row in the Aventurero section."""
    in_section = False
    for line in text.splitlines():
        if line.startswith("## Aventurero"):
            in_section = True
        elif in_section and line.startswith("| adventurer-sago |"):
            return line.rsplit("|", 2)[1].strip()
    raise AssertionError("adventurer-sago row not found")


def _resolve_guild_board(working, quest_id, *, tier, force, claimant="adventurer-sago"):
    """Register a resolved guild board and mark it success this tick."""
    working["quests"]["resolved"][quest_id] = {
        "id": quest_id, "type": "raid", "tier": "minor",
        "eligibility": "adventurer", "max_claimants": "open",
        "deadline": 5, "reward": 6, "stake": 1, "progress": {},
        "claimed_by": [claimant], "resolved_tick": 1, "status": "success",
        "params": {"force": force, "region": "ring-3", "guild_tier": tier},
    }
    working["tick_events"]["quests_resolved"][quest_id] = "success"


def test_sanctuary_token(state):
    working = copy.deepcopy(state)
    working["tick_events"]["sanctuary_activated"] = ["adventurer-sago"]
    assert "santuario" in _adventurer_events(resolve_chronicle(working, [], CONFIG, SEED)["chronicle"])


def test_gremio_token(state):
    working = copy.deepcopy(state)
    _resolve_guild_board(working, "guild-1-1", tier="bronze", force="force-1")
    events = _adventurer_events(resolve_chronicle(working, [], CONFIG, SEED)["chronicle"])
    assert "gremio:bronze@force-1" in events


def test_non_guild_board_success_emits_no_gremio_token(state):
    # the fixture already resolves raid-0-1 (success) with no guild_tier
    events = _adventurer_events(resolve_chronicle(state, [], CONFIG, SEED)["chronicle"])
    assert "gremio:" not in events


def test_capability_token(state):
    working = copy.deepcopy(state)
    working["tick_events"]["capability_grants"] = {"adventurer-sago": ["swift_march"]}
    events = _adventurer_events(resolve_chronicle(working, [], CONFIG, SEED)["chronicle"])
    assert "capacidad:+swift_march" in events


def test_rango_token_when_rank_rises(state):
    working = copy.deepcopy(state)
    working["adventurers"]["adventurer-sago"]["guild"] = {"force-1": {"completed": ["bronze"]}}
    working["tick_events"]["guild_completions"] = {"adventurer-sago": {"force-1": ["bronze"]}}
    events = _adventurer_events(resolve_chronicle(working, [], CONFIG, SEED)["chronicle"])
    assert "rango:force-1=bronze" in events


def test_no_rango_token_when_completion_does_not_raise_rank(state):
    working = copy.deepcopy(state)
    # silver already held; completing bronze this tick does not raise the ceiling
    working["adventurers"]["adventurer-sago"]["guild"] = {
        "force-1": {"completed": ["bronze", "silver"]}
    }
    working["tick_events"]["guild_completions"] = {"adventurer-sago": {"force-1": ["bronze"]}}
    events = _adventurer_events(resolve_chronicle(working, [], CONFIG, SEED)["chronicle"])
    assert "rango:" not in events


def test_guild_tokens_render_in_resolution_order(state):
    working = copy.deepcopy(state)
    working["tick_events"]["adventurer_spawned"] = ["adventurer-sago"]
    working["tick_events"]["sanctuary_activated"] = ["adventurer-sago"]
    working["tick_events"]["loot_claims"] = {"adventurer-sago": 3}
    working["tick_events"]["capability_grants"] = {"adventurer-sago": ["sanctuary"]}
    working["adventurers"]["adventurer-sago"]["guild"] = {"force-1": {"completed": ["bronze"]}}
    working["tick_events"]["guild_completions"] = {"adventurer-sago": {"force-1": ["bronze"]}}
    _resolve_guild_board(working, "guild-1-1", tier="bronze", force="force-1")
    events = _adventurer_events(resolve_chronicle(working, [], CONFIG, SEED)["chronicle"])
    assert events == (
        "spawn; move:capital-2; santuario; botín:+3; "
        "gremio:bronze@force-1; capacidad:+sanctuary; rango:force-1=bronze"
    )
