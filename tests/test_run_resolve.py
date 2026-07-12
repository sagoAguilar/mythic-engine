import shutil
from pathlib import Path

from scripts.run_resolve import run

REPO_ROOT = Path(__file__).resolve().parent.parent
FULL_TICK = REPO_ROOT / "tests" / "fixtures" / "full_tick"


def test_run_resolves_tick_after_the_one_in_tick_txt(tmp_path):
    root = tmp_path / "repo"
    shutil.copytree(FULL_TICK, root)
    assert (root / "world" / "tick.txt").read_text().strip() == "0"

    state = run(root)

    assert state["tick"] == 1
    assert (root / "chronicle" / "tick-1.md").exists()
    assert (root / "world" / "tick.txt").read_text().strip() == "1"


def test_run_is_a_thin_shell_matching_direct_resolve_call(tmp_path):
    # same fixture resolved two ways - via run_resolve's wiring, and via
    # a direct engine.resolve() call - must agree byte for byte
    from engine import resolve as direct_resolve
    from engine.config import load_era_config

    via_wrapper = tmp_path / "wrapper"
    via_direct = tmp_path / "direct"
    shutil.copytree(FULL_TICK, via_wrapper)
    shutil.copytree(FULL_TICK, via_direct)

    run(via_wrapper)
    seed = load_era_config(via_direct / "world" / "era.yml").era.seed
    direct_resolve(via_direct, via_direct / "moves" / "tick-1", seed)

    files_wrapper = {
        p.relative_to(via_wrapper): p.read_bytes()
        for p in via_wrapper.rglob("*") if p.is_file()
    }
    files_direct = {
        p.relative_to(via_direct): p.read_bytes()
        for p in via_direct.rglob("*") if p.is_file()
    }
    assert files_wrapper == files_direct
