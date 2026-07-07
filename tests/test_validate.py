from pathlib import Path

import pytest
import yaml

from engine.config import load_era_config
from engine.validate import ValidationError, validate_move, validate_world
from scripts.generate_map import build_map

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "moves"
CONFIG = load_era_config(REPO_ROOT / "world" / "era.yml")

ACTIONS = [
    "move_units",
    "attack_region",
    "recruit",
    "fortify",
    "accept_quest",
    "spawn_adventurer",
    "claim_loot",
]


def _load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# --- move batches -----------------------------------------------------------


@pytest.mark.parametrize("action", ACTIONS)
def test_valid_move_fixture_passes(action):
    validate_move(_load(FIXTURES / "valid" / f"{action}.yml"), CONFIG)


@pytest.mark.parametrize("action", ACTIONS)
def test_invalid_move_fixture_fails(action):
    with pytest.raises(ValidationError):
        validate_move(_load(FIXTURES / "invalid" / f"{action}.yml"), CONFIG)


def test_fixtures_cover_every_action_type():
    for kind in ("valid", "invalid"):
        assert sorted(p.stem for p in (FIXTURES / kind).glob("*.yml")) == sorted(ACTIONS)


def test_force_order_cap_enforced_from_config():
    batch = _load(FIXTURES / "valid" / "move_units.yml")
    order = batch["orders"][0]
    batch["orders"] = [order] * (CONFIG.orders.cap_force + 1)
    with pytest.raises(ValidationError, match=f"cap {CONFIG.orders.cap_force}"):
        validate_move(batch, CONFIG)


def test_adventurer_order_cap_enforced_from_config():
    batch = _load(FIXTURES / "valid" / "claim_loot.yml")
    order = batch["orders"][0]
    batch["orders"] = [order] * (CONFIG.orders.cap_adventurer + 1)
    with pytest.raises(ValidationError, match=f"cap {CONFIG.orders.cap_adventurer}"):
        validate_move(batch, CONFIG)


def test_unknown_action_fails():
    batch = _load(FIXTURES / "valid" / "fortify.yml")
    batch["orders"][0]["action"] = "gather"  # removed from the catalog
    with pytest.raises(ValidationError):
        validate_move(batch, CONFIG)


# --- world state ------------------------------------------------------------


def _valid_world():
    era = yaml.safe_load((REPO_ROOT / "world" / "era.yml").read_text(encoding="utf-8"))
    return {
        "era": era,
        "tick": 0,
        "regions": build_map(3, CONFIG.economy),
        "forces": {
            f"force-{i}": {
                "id": f"force-{i}",
                "persona": f"personas/force-{i}.md",
                "essence": 0,
                "units": 0,
            }
            for i in (1, 2, 3)
        },
        "adventurers": {
            "adventurer-sago": {
                "id": "adventurer-sago",
                "name": "Wanderer",
                "controller": "github:sagoAguilar",
                "essence": CONFIG.adventurer.baseline_essence,
                "position": "ring-1",
                "units": 1,
                "reputation": {f"force-{i}": 0 for i in (1, 2, 3)},
                "capabilities": [],
                "personal_quest": {"type": "survive", "target": "era"},
            }
        },
        "quests": {
            "active": {
                "raid-7-1": {
                    "id": "raid-7-1",
                    "type": "raid",
                    "tier": "minor",
                    "eligibility": "any",
                    "reward": 6,
                    "stake": 1,
                    "deadline": 15,
                    "max_claimants": "open",
                    "claimed_by": [],
                    "params": {"region": "arm-2-a"},
                }
            },
            "resolved": {},
        },
        "graveyard": [
            {
                "id": "adventurer-elder",
                "name": "Elder",
                "controller": "github:someone-else",
                "died_tick": 42,
                "era": 1,
                "titles": [],
            }
        ],
    }


def test_valid_world_passes():
    validate_world(_valid_world())


def test_world_with_negative_units_fails():
    world = _valid_world()
    world["regions"]["ring-1"]["units"] = -1
    with pytest.raises(ValidationError, match="ring-1"):
        validate_world(world)


def test_world_missing_section_fails():
    world = _valid_world()
    del world["quests"]
    with pytest.raises(ValidationError, match="quests"):
        validate_world(world)


def test_world_with_unknown_region_field_fails():
    world = _valid_world()
    world["regions"]["capital-1"]["mana"] = 3
    with pytest.raises(ValidationError):
        validate_world(world)
