"""Phase 7 of the resolution order: economic yield on post-combat ownership.

Passive income (docs/intent.md: ``gather`` was eliminated): every owned
region pays its ``yield`` to its owner, judged on post-combat ownership
— taking a region this tick earns this tick, losing one earns nothing.
Ownership alone pays; a scorched 0-unit region still yields. Neutral
regions pay nobody, and the adventurer owns nothing. Yield values are
read from region state (populated from era.yml by the map generator),
never hardcoded.

This phase also dissipates stale loot: a pot whose ``expires_tick`` is
behind the resolving tick became unclaimable when phase 6's window
passed ("reclamable por M ticks, luego se disipa") and is removed.

Pure function: no input mutation, no I/O, no randomness. ``moves``,
``config``, and ``seed`` are part of the uniform phase signature and
unused — this phase is driven entirely by state.
"""


def resolve_yield(state: dict, moves: list, config, seed: int) -> dict:
    """(state, moves, config, seed) -> phase-7 state delta.

    Returns a dict with:
      essence_changes: {force_id: yield income}
      loot_changes:    {region_id: None} for every dissipated stale pot
    """
    tick = state["tick"] + 1

    essence_changes: dict[str, int] = {}
    loot_changes: dict[str, None] = {}

    for region_id in sorted(state["regions"]):
        region = state["regions"][region_id]
        owner = region["owner"]
        if owner is not None:
            essence_changes[owner] = essence_changes.get(owner, 0) + region["yield"]
        loot = region["loot"]
        if loot is not None and loot["expires_tick"] < tick:
            loot_changes[region_id] = None

    return {
        "essence_changes": dict(sorted(essence_changes.items())),
        "loot_changes": loot_changes,
    }
