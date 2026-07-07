"""Phase 5 of the resolution order: combat resolution (F1 over F2 ladders).

Consumes the ``pending_combats`` staged by phase 4 (carried on the
working state — the resolver applies each phase's delta before the
next). The seed never touches combat: party order was fixed by phase 4's
seeded formula, and F1 itself is strict determinism.

F1 (frozen): attacker power = attacking units; defender power =
defending units + fortification x fortify_bonus. Attacker wins strictly
above defender power, taking the region with the difference as
survivors and annihilating the defender; otherwise the attacker is
annihilated and the defender loses max(0, attacker - fort x bonus).
Ties favor the defender.

F2 incumbency ladder: the standing garrison is the incumbent; each
party in staged (hash) order attacks the current incumbent; the winner
becomes incumbent. A neutral collision starts from an empty incumbent.
Fortification is a structure of the region and persists through
capture, defending whoever currently holds it — including a mid-ladder
captor.

The hunt (attack_region, target: adventurer, F4): a landed declaration
kills the coexisting non-combatant outright — no F1 duel; the cost is
the order slot and the units' commitment. The hunt lands against the
adventurer's post-move position (simultaneity: a same-tick move
dodges). The committed units then act as a normal party toward the
region: merging with an own garrison, fighting F1 otherwise. On death,
ceil(essence x loot_burn_fraction) burns; the rest deposits as regional
loot expiring after loot_dissipation_ticks — collected immediately by
the killer only if it controls the region post-combat, merged into any
existing loot otherwise. The entity moves to the graveyard and the
username is freed.

Pure function: no input mutation, no I/O, no wall clock.
"""

import math


def _f1(attacker_units: int, defender_units: int, fort: int, bonus: int):
    """One F1 resolution. Returns (attacker_won, attacker_survivors,
    defender_survivors)."""
    defender_power = defender_units + fort * bonus
    if attacker_units > defender_power:
        return True, attacker_units - defender_power, 0
    loss = max(0, attacker_units - fort * bonus)
    return False, 0, defender_units - loss


def resolve_combat(state: dict, moves: list, config, seed: int) -> dict:
    """(state, moves, config, seed) -> phase-5 state delta.

    ``state`` is the post-phase-4 working state and must carry the
    transient ``pending_combats`` key; ``moves`` and ``seed`` are part
    of the uniform phase signature and unused here.

    Returns a dict with:
      unit_changes:        {region_id: net garrison delta}
      owner_changes:       {region_id: new owner}
      essence_changes:     {force_id: loot collected by a controlling killer}
      loot_changes:        {region_id: loot object deposited}
      adventurer_deaths:   [{id, region, killer}]
      graveyard_additions: [full graveyard entries]
      combats:             [{region, rounds: [...]}] full F1 trace per ladder
      combat_regions:      sorted regions where units were destroyed or a
                           hunt landed — the next state's combats_last_tick
    """
    tick = state["tick"] + 1
    regions = state["regions"]

    unit_changes: dict[str, int] = {}
    owner_changes: dict[str, str] = {}
    essence_changes: dict[str, int] = {}
    loot_changes: dict[str, dict] = {}
    deaths: list[dict] = []
    graveyard_additions: list[dict] = []
    combats: list[dict] = []
    combat_regions: set[str] = set()
    dead: set[str] = set()

    for staged in state.get("pending_combats", []):
        region_id = staged["region"]
        region = regions[region_id]
        incumbent_owner = region["owner"]
        incumbent_units = region["units"]
        fort = region["fortification"]
        start_units = incumbent_units
        rounds: list[dict] = []
        kills_here: list[tuple[str, int]] = []  # (killer, deposit)

        for party in staged["parties"]:
            actor, count = party["actor"], party["count"]

            if party.get("target") == "adventurer":
                victim_id = next(
                    (aid for aid, adv in sorted(state["adventurers"].items())
                     if adv["position"] == region_id and aid not in dead),
                    None,
                )
                if victim_id is not None:
                    victim = state["adventurers"][victim_id]
                    dead.add(victim_id)
                    burn = math.ceil(
                        victim["essence"] * config.adventurer.loot_burn_fraction
                    )
                    kills_here.append((actor, victim["essence"] - burn))
                    deaths.append(
                        {"id": victim_id, "region": region_id, "killer": actor}
                    )
                    graveyard_additions.append({
                        "id": victim_id,
                        "name": victim["name"],
                        "controller": victim["controller"],
                        "died_tick": tick,
                        "era": config.era.number,
                        "titles": [],
                    })
                    combat_regions.add(region_id)

            if actor == incumbent_owner:
                incumbent_units += count  # own garrison: merge, no combat
                continue

            won, attacker_survivors, defender_survivors = _f1(
                count, incumbent_units, fort, config.economy.fortify_bonus
            )
            rounds.append({
                "attacker": actor,
                "attacker_units": count,
                "defender": incumbent_owner,
                "defender_units": incumbent_units,
                "defender_power": incumbent_units + fort * config.economy.fortify_bonus,
                "winner": actor if won else incumbent_owner,
                "attacker_survivors": attacker_survivors,
                "defender_survivors": defender_survivors,
            })
            if count > attacker_survivors or incumbent_units > defender_survivors:
                combat_regions.add(region_id)
            if won:
                incumbent_owner, incumbent_units = actor, attacker_survivors
            else:
                incumbent_units = defender_survivors

        if incumbent_units != start_units:
            unit_changes[region_id] = incumbent_units - start_units
        if incumbent_owner != region["owner"]:
            owner_changes[region_id] = incumbent_owner
        combats.append({"region": region_id, "rounds": rounds})

        for killer, deposit in kills_here:
            if deposit <= 0:
                continue
            if killer == incumbent_owner:
                essence_changes[killer] = essence_changes.get(killer, 0) + deposit
            else:
                base = loot_changes.get(region_id) or region["loot"]
                if base is not None:
                    loot_changes[region_id] = {
                        "essence": base["essence"] + deposit,
                        "expires_tick": max(
                            base["expires_tick"],
                            tick + config.adventurer.loot_dissipation_ticks,
                        ),
                    }
                else:
                    loot_changes[region_id] = {
                        "essence": deposit,
                        "expires_tick": tick + config.adventurer.loot_dissipation_ticks,
                    }

    return {
        "unit_changes": dict(sorted(unit_changes.items())),
        "owner_changes": dict(sorted(owner_changes.items())),
        "essence_changes": dict(sorted(essence_changes.items())),
        "loot_changes": dict(sorted(loot_changes.items())),
        "adventurer_deaths": deaths,
        "graveyard_additions": graveyard_additions,
        "combats": combats,
        "combat_regions": sorted(combat_regions),
    }
