"""The master test (CLAUDE.md definition of done).

Resolving the same fixture twice must produce byte-identical output
directory trees. Until this passes, nothing else matters — and nothing
merges after this point if it is red.
"""

import shutil
from pathlib import Path

from engine import resolve
from engine.config import load_era_config
from engine.resolve import load_state

REPO_ROOT = Path(__file__).resolve().parent.parent
FULL_TICK = REPO_ROOT / "tests" / "fixtures" / "full_tick"
FULL_TICK_CHAIN = REPO_ROOT / "tests" / "fixtures" / "full_tick_chain"
SEED = load_era_config(REPO_ROOT / "world" / "era.yml").era.seed


def _resolved_copy(fixture: Path, tmp_path: Path, name: str, ticks: range) -> Path:
    root = tmp_path / name
    shutil.copytree(fixture, root)
    for tick in ticks:
        resolve(root, root / "moves" / f"tick-{tick}", SEED)
    return root


def _tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_master_single_tick_is_byte_identical(tmp_path):
    first = _resolved_copy(FULL_TICK, tmp_path, "first", range(1, 2))
    second = _resolved_copy(FULL_TICK, tmp_path, "second", range(1, 2))
    assert _tree(first) == _tree(second)

    # the tick actually happened: pointer advanced, chronicle written,
    # output re-loads as schema-valid state
    assert (first / "world" / "tick.txt").read_text() == "1\n"
    chronicle = (first / "chronicle" / "tick-1.md").read_text(encoding="utf-8")
    assert chronicle.startswith("# Crónica — era 1 — tick 1")
    state = load_state(first)  # validates against world.schema.json
    # the spawn carve-out landed: the elder exists and lives at arm-1-b
    assert state["adventurers"]["adventurer-elder"]["position"] == "arm-1-b"


def test_master_three_tick_chain_is_byte_identical(tmp_path):
    first = _resolved_copy(FULL_TICK_CHAIN, tmp_path, "first", range(1, 4))
    second = _resolved_copy(FULL_TICK_CHAIN, tmp_path, "second", range(1, 4))
    assert _tree(first) == _tree(second)

    assert (first / "world" / "tick.txt").read_text() == "3\n"
    for tick in (1, 2, 3):
        assert (first / "chronicle" / f"tick-{tick}.md").exists()
    # tick 3 had no submissions: every actor ran on the NPC policy
    tick3 = (first / "chronicle" / "tick-3.md").read_text(encoding="utf-8")
    assert "| agent |" not in tick3
    assert "| human |" not in tick3
    load_state(first)  # final state is schema-valid


def test_chain_ticks_differ_from_each_other(tmp_path):
    # sanity against a frozen world: consecutive chronicles are distinct
    root = _resolved_copy(FULL_TICK_CHAIN, tmp_path, "run", range(1, 4))
    texts = [
        (root / "chronicle" / f"tick-{t}.md").read_text(encoding="utf-8")
        for t in (1, 2, 3)
    ]
    assert len(set(texts)) == 3
