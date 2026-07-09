from pathlib import Path

from engine.config import load_era_config
from engine.resolve import load_state
from engine.validate import validate_world
from scripts.seed_era import seed_world, write_world

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG = load_era_config(REPO_ROOT / "world" / "era.yml")


def test_seed_world_produces_schema_valid_tick_zero_state(tmp_path):
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    world_dir.joinpath("era.yml").write_text(
        (REPO_ROOT / "world" / "era.yml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    files = seed_world(CONFIG)
    write_world(files, world_dir)

    state = load_state(tmp_path)  # validates against world.schema.json

    assert state["tick"] == 0
    assert len(state["regions"]) == 12
    for i in (1, 2, 3):
        capital = state["regions"][f"capital-{i}"]
        assert capital["owner"] == f"force-{i}"
        assert capital["units"] == CONFIG.bootstrap.starting_units_capital
        assert state["forces"][f"force-{i}"]["essence"] == CONFIG.bootstrap.starting_essence
    neutrals = [r for r in state["regions"].values() if r["owner"] is None]
    assert len(neutrals) == 9
    assert all(r["units"] == 0 for r in neutrals)
    assert state["adventurers"] == {}
    assert state["graveyard"] == []
    assert state["supremacy"] == {
        "leader": None,
        "streaks": {"force-1": 0, "force-2": 0, "force-3": 0},
    }
