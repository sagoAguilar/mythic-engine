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

Siege upkeep-or-collapse (F6) is paid last, from whatever essence
remains after unit and fortify upkeep: each active siege costs its
attacker a flat ``economy.siege_upkeep`` that tick. Unpayable ends the
siege immediately (no partial erosion, no grace). Paid sieges advance
``ticks_elapsed``; when it lands on a multiple of
``economy.siege_erosion_interval``, the besieged region loses one
fortification level (sharing the same never-below-0 floor as fortify
upkeep's own erosion — the two can stack on the same region and are
tracked together). A siege also ends the instant its target changes
owner by any means (checked first, before any upkeep is charged) or its
fortification reaches 0. On any ending, the committed units return to
their origin region if the attacker still owns it, otherwise they're
lost. A siege started this same tick (phase 4) is not yet visible here
— it owes nothing and erodes nothing until next tick's phase 7.

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
      fortification_changes: {region_id: net delta} fortify-upkeep erosion
                              and/or siege erosion, summed per region
      unit_changes:          {region_id: units returned by an ended siege}
      loot_changes:           {region_id: None} for every dissipated stale pot
      sieges_ended:           [region_id, ...] to drop from persistent state
      siege_progress:         {region_id: new ticks_elapsed} for survivors
    """
    tick = state["tick"] + 1
    regions = state["regions"]
    sieges = state.get("sieges", {})

    essence_changes: dict[str, int] = {}
    fortification_changes: dict[str, int] = {}
    unit_changes: dict[str, int] = {}
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

    sieges_ended: list[str] = []
    siege_progress: dict[str, int] = {}

    def end_siege(region_id: str) -> None:
        sieges_ended.append(region_id)
        siege = sieges[region_id]
        if regions[siege["from"]]["owner"] == siege["attacker"]:
            unit_changes[siege["from"]] = unit_changes.get(siege["from"], 0) + siege["units"]

    # a siege whose target already changed hands is moot - end it before
    # any upkeep is charged, regardless of who now holds the region
    for region_id in sorted(sieges):
        if regions[region_id]["owner"] != sieges[region_id]["defender"]:
            end_siege(region_id)
    ended = set(sieges_ended)

    sieges_by_attacker: dict[str, list[str]] = {}
    for region_id, siege in sieges.items():
        if region_id not in ended:
            sieges_by_attacker.setdefault(siege["attacker"], []).append(region_id)

    for force_id in sorted(set(owned_regions) | set(sieges_by_attacker)):
        fortified = sorted(
            (rid for rid in owned_regions.get(force_id, []) if regions[rid]["fortification"] > 0),
            key=lambda rid: (regions[rid]["fortification"], rid),
        )
        active_sieges = sorted(sieges_by_attacker.get(force_id, []))
        if not fortified and not active_sieges:
            continue

        remaining = state["forces"][force_id]["essence"] + essence_changes.get(force_id, 0)

        for region_id in fortified:
            cost = config.economy.fortify_upkeep.at_level(regions[region_id]["fortification"])
            if remaining >= cost:
                remaining -= cost
                essence_changes[force_id] = essence_changes.get(force_id, 0) - cost
            else:
                effective_level = regions[region_id]["fortification"] + fortification_changes.get(region_id, 0)
                if effective_level > 0:
                    fortification_changes[region_id] = fortification_changes.get(region_id, 0) - 1

        for region_id in active_sieges:
            cost = config.economy.siege_upkeep
            if remaining < cost:
                end_siege(region_id)
                continue
            remaining -= cost
            essence_changes[force_id] = essence_changes.get(force_id, 0) - cost
            elapsed = sieges[region_id]["ticks_elapsed"] + 1
            if elapsed % config.economy.siege_erosion_interval == 0:
                effective_level = regions[region_id]["fortification"] + fortification_changes.get(region_id, 0)
                if effective_level > 0:
                    fortification_changes[region_id] = fortification_changes.get(region_id, 0) - 1
                    effective_level -= 1
                if effective_level <= 0:
                    end_siege(region_id)
                    continue
            siege_progress[region_id] = elapsed

    return {
        "essence_changes": dict(sorted(essence_changes.items())),
        "fortification_changes": dict(sorted(fortification_changes.items())),
        "unit_changes": dict(sorted(unit_changes.items())),
        "loot_changes": loot_changes,
        "sieges_ended": sorted(sieges_ended),
        "siege_progress": dict(sorted(siege_progress.items())),
    }
