import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from engine.config import load_era_config
from scripts.generate_map import build_map

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG = load_era_config(REPO_ROOT / "world" / "era.yml")


def _adjacency(regions):
    return {rid: set(r["adjacent"]) for rid, r in regions.items()}


def test_structure_for_three_arms():
    regions = build_map(3, CONFIG.economy)
    assert len(regions) == 12

    adjacency = _adjacency(regions)
    # symmetric adjacency: every edge is listed on both endpoints
    for rid, neighbors in adjacency.items():
        for n in neighbors:
            assert rid in adjacency[n]

    degrees = {rid: len(n) for rid, n in adjacency.items()}
    assert sum(degrees.values()) // 2 == 15
    assert min(degrees.values()) == 2
    assert max(degrees.values()) == 4
    # capitals have exactly 2 entry routes
    for i in (1, 2, 3):
        assert degrees[f"capital-{i}"] == 2


def test_ownership_and_yields():
    regions = build_map(3, CONFIG.economy)
    for i in (1, 2, 3):
        assert regions[f"capital-{i}"]["owner"] == f"force-{i}"
        assert regions[f"capital-{i}"]["yield"] == CONFIG.economy.yield_capital
        assert regions[f"ring-{i}"]["owner"] is None
        assert regions[f"ring-{i}"]["yield"] == CONFIG.economy.yield_ring
        for side in ("a", "b"):
            assert regions[f"arm-{i}-{side}"]["owner"] is None
            assert regions[f"arm-{i}-{side}"]["yield"] == CONFIG.economy.yield_neutral
    # 9 spawnable neutrals at tick 0
    assert sum(1 for r in regions.values() if r["owner"] is None) == 9


def test_rotational_isomorphism():
    arms = 3
    adjacency = _adjacency(build_map(arms, CONFIG.economy))

    for shift in range(1, arms):

        def rotate(rid):
            kind, num, *rest = rid.split("-")
            rotated = (int(num) - 1 + shift) % arms + 1
            return "-".join([kind, str(rotated), *rest])

        relabeled = {rotate(rid): {rotate(n) for n in ns} for rid, ns in adjacency.items()}
        assert relabeled == adjacency


def test_rejects_degenerate_arm_count():
    with pytest.raises(ValueError, match="arms"):
        build_map(2, CONFIG.economy)


def test_cli_emits_region_files_deterministically(tmp_path):
    outputs = []
    for name in ("run1", "run2"):
        out = tmp_path / name
        subprocess.run(
            [sys.executable, "scripts/generate_map.py",
             "--seed", "20260706", "--arms", "3", "--out", str(out)],
            check=True, cwd=REPO_ROOT, capture_output=True,
        )
        outputs.append(out)

    names = sorted(p.name for p in outputs[0].iterdir())
    assert len(names) == 12
    assert names == sorted(p.name for p in outputs[1].iterdir())
    for name in names:
        assert (outputs[0] / name).read_bytes() == (outputs[1] / name).read_bytes()

    capital = yaml.safe_load((outputs[0] / "capital-1.yml").read_text(encoding="utf-8"))
    assert capital["owner"] == "force-1"
    assert capital["yield"] == CONFIG.economy.yield_capital
    assert sorted(capital["adjacent"]) == ["arm-1-a", "arm-1-b"]
