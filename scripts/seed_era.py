#!/usr/bin/env python3
"""Seed the real era-1 tick-0 world state under world/.

Builds the map (scripts/generate_map.py), sets each capital's starting
garrison and each force's starting essence from era.yml's bootstrap
block (provisional, not calibrated), and writes the remaining state
files the resolver expects: tick.txt, combats_last_tick.yml,
supremacy.yml, and empty forces/adventurers/quests/graveyard.

Usage: python scripts/seed_era.py [--out DIR]
"""

import argparse
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from engine.config import load_era_config  # noqa: E402
from scripts.generate_map import build_map  # noqa: E402


def seed_world(config) -> dict:
    """Return {relative_path: yaml-serializable data} for world/."""
    regions = build_map(config.map.arms, config.economy)
    for region in regions.values():
        if region["owner"] is not None:
            region["units"] = config.bootstrap.starting_units_capital

    forces = {
        f"force-{i}": {
            "id": f"force-{i}",
            "persona": f"personas/force-{i}.md",
            "essence": config.bootstrap.starting_essence,
            "units": config.bootstrap.starting_units_capital,
        }
        for i in range(1, config.map.arms + 1)
    }

    files: dict[str, object] = {"tick.txt": "0\n"}
    files["combats_last_tick.yml"] = []
    files["supremacy.yml"] = {
        "leader": None,
        "streaks": {force_id: 0 for force_id in forces},
    }
    for region_id, region in regions.items():
        files[f"regions/{region_id}.yml"] = region
    for force_id, force in forces.items():
        files[f"forces/{force_id}.yml"] = force
    return files


def write_world(files: dict, out_dir: Path) -> None:
    for relative, data in files.items():
        path = out_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, str):
            path.write_text(data, encoding="utf-8")
        else:
            path.write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "world",
                        help="world/ directory to seed (default: repo root world/)")
    args = parser.parse_args(argv)

    config = load_era_config(args.out / "era.yml")
    files = seed_world(config)
    write_world(files, args.out)
    print(f"seeded {len(files)} files under {args.out} (era {config.era.number}, tick 0)")


if __name__ == "__main__":
    main()
