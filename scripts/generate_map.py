#!/usr/bin/env python3
"""Generate the initial region files for an era.

Topology frozen in docs/intent.md (map section): k identical arms, each a
capital feeding two neutrals, converging on a central ring of k neutrals.
Edges per arm i: C-A, C-B, A-R_i, B-R_i; ring cycle R_1..R_k. For k=3 that
is 12 regions, 15 edges, degree 2-4, capitals with exactly 2 entry routes.

Yields come from world/era.yml (neutral 1, capital and ring 2 in era 1),
never hardcoded here. The graph is symmetric by construction, so --seed
does not influence the topology; the flag exists to match the frozen CLI
signature in docs/intent.md.

Usage: python scripts/generate_map.py --seed N [--arms k] [--out DIR]
"""

import argparse
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from engine.config import Economy, load_era_config  # noqa: E402


def build_map(arms: int, economy: Economy) -> dict[str, dict]:
    """Return the initial regions as {region_id: region_dict}.

    Region ids: capital-<i>, arm-<i>-a, arm-<i>-b, ring-<i> for arm i in
    1..arms. Capitals are owned by force-<i>; everything else is neutral
    (owner null). Units, fortification, and loot start at the empty state;
    era bootstrap fills in starting garrisons.
    """
    if arms < 3:
        raise ValueError("arms must be >= 3: the ring cycle degenerates below 3")

    regions: dict[str, dict] = {}

    def add(region_id: str, owner: str | None, region_yield: int) -> None:
        regions[region_id] = {
            "id": region_id,
            "owner": owner,
            "yield": region_yield,
            "adjacent": set(),
            "units": 0,
            "fortification": 0,
            "loot": None,
        }

    def connect(a: str, b: str) -> None:
        regions[a]["adjacent"].add(b)
        regions[b]["adjacent"].add(a)

    for i in range(1, arms + 1):
        add(f"capital-{i}", f"force-{i}", economy.yield_capital)
        add(f"arm-{i}-a", None, economy.yield_neutral)
        add(f"arm-{i}-b", None, economy.yield_neutral)
        add(f"ring-{i}", None, economy.yield_ring)

    for i in range(1, arms + 1):
        connect(f"capital-{i}", f"arm-{i}-a")
        connect(f"capital-{i}", f"arm-{i}-b")
        connect(f"arm-{i}-a", f"ring-{i}")
        connect(f"arm-{i}-b", f"ring-{i}")
        connect(f"ring-{i}", f"ring-{i % arms + 1}")

    for region in regions.values():
        region["adjacent"] = sorted(region["adjacent"])
    return regions


def write_regions(regions: dict[str, dict], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for region_id in sorted(regions):
        text = yaml.safe_dump(regions[region_id], sort_keys=True)
        (out_dir / f"{region_id}.yml").write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, required=True,
                        help="era seed (recorded interface; topology is symmetric by construction)")
    parser.add_argument("--arms", type=int, default=None,
                        help="number of arms/forces (default: map.arms from world/era.yml)")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "world" / "regions",
                        help="output directory (default: world/regions/)")
    args = parser.parse_args(argv)

    config = load_era_config(REPO_ROOT / "world" / "era.yml")
    arms = args.arms if args.arms is not None else config.map.arms
    regions = build_map(arms, config.economy)
    write_regions(regions, args.out)
    print(f"wrote {len(regions)} regions to {args.out}")


if __name__ == "__main__":
    main()
