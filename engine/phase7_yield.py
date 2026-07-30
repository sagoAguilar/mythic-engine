"""Phase 7 of the resolution order: economic yield on post-combat ownership.

Passive income (docs/intent.md: ``gather`` was eliminated): every owned
region pays its ``yield`` to its owner, judged on post-combat ownership
— taking a region this tick earns this tick, losing one earns nothing.
Ownership alone pays; a scorched 0-unit region still yields. Neutral
regions pay nobody, and the adventurer owns nothing. Yield values are
read from region state (populated from era.yml by the map generator),
never hardcoded.

Upkeep (F5) nets against that same yield, in the same phase: each force
pays ``floor(total_units / economy.upkeep_divisor)`` essence per tick,
computed from post-combat garrison across all of its regions. A force
holding fewer than ``upkeep_divisor`` units pays nothing — this is
deliberately a cost that only bites once a force's army has actually
grown, not a tax on the opening game.

Fortify upkeep-or-erosion (F5, second sink) is paid after unit upkeep,
from whatever essence remains: each region a force owns with
fortification > 0 owes ``economy.fortify_upkeep.at_level(level)`` that
tick. A force pays its fortified regions in ascending (level, region_id)
order — cheapest commitment first — until its remaining essence runs
out; every region it can't afford erodes exactly one fortification
level (never below 0) instead of essence going negative. No refund, no
extra penalty beyond the lost level.

This phase also dissipates stale loot: a pot whose ``expires_tick`` is
behind the resolving tick became unclaimable when phase 6's window
passed ("reclamable por M ticks, luego se disipa") and is removed.

Pure function: no input mutation, no I/O, no randomness. ``moves`` and
``seed`` are part of the uniform phase signature and unused — this
phase is driven entirely by state and ``config``.
"""


def resolve_yield(state: dict, moves: list, config, seed: int) -> dict:
    """(state, moves, config, seed) -> phase-7 state delta.

    Returns a dict with:
      essence_changes:       {force_id: net yield income minus upkeep}
      fortification_changes: {region_id: -1} for each region that eroded
      loot_changes:           {region_id: None} for every dissipated stale pot
    """
    tick = state["tick"] + 1
    regions = state["regions"]

    essence_changes: dict[str, int] = {}
    fortification_changes: dict[str, int] = {}
    loot_changes: dict[str, None] = {}
    units_owned: dict[str, int] = {}
    owned_regions: dict[str, list[str]] = {}

    for region_id in sorted(regions):
        region = regions[region_id]
        owner = region["owner"]
        if owner is not None:
            essence_changes[owner] = essence_changes.get(owner, 0) + region["yield"]
            units_owned[owner] = units_owned.get(owner, 0) + region["units"]
            owned_regions.setdefault(owner, []).append(region_id)
        loot = region["loot"]
        if loot is not None and loot["expires_tick"] < tick:
            loot_changes[region_id] = None

    for force_id in sorted(units_owned):
        upkeep = units_owned[force_id] // config.economy.upkeep_divisor
        if upkeep:
            essence_changes[force_id] = essence_changes.get(force_id, 0) - upkeep

    for force_id in sorted(owned_regions):
        fortified = sorted(
            (rid for rid in owned_regions[force_id] if regions[rid]["fortification"] > 0),
            key=lambda rid: (regions[rid]["fortification"], rid),
        )
        if not fortified:
            continue
        remaining = state["forces"][force_id]["essence"] + essence_changes.get(force_id, 0)
        for region_id in fortified:
            cost = config.economy.fortify_upkeep.at_level(regions[region_id]["fortification"])
            if remaining >= cost:
                remaining -= cost
                essence_changes[force_id] = essence_changes.get(force_id, 0) - cost
            else:
                fortification_changes[region_id] = -1

    return {
        "essence_changes": dict(sorted(essence_changes.items())),
        "fortification_changes": dict(sorted(fortification_changes.items())),
        "loot_changes": loot_changes,
    }
