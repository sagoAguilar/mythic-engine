"""Phase 1 of the resolution order: schema validation + NPC substitution.

Single code path for absence and failure (docs/intent.md): a missing,
malformed, duplicated, or wrong-tick batch is replaced wholesale by the
deterministic NPC policy, marked origin ``npc`` so those ticks are
excluded from analysis. State-level preconditions (adjacency, unit
counts, essence) are NOT checked here — each later phase enforces its
own catalog preconditions order by order.

Frozen NPC policy (max 1 order regardless of caps — the volume gap is
part of the trace):

Force: (1) own region saw combat last tick and essence >= recruit_cost
-> recruit 1 in the own region with fewest units (tiebreak: lowest
lexical id); (2) essence >= fortify_cost and own capital (by the frozen
naming convention capital-<n> for force-<n>) below the fortification
cap -> fortify it; (3) a neutral borders the force -> move half
(floor) of the units of the neutral-adjacent own region with most
units (tiebreaks: lowest destination id, then lowest origin id; a half
of zero falls through); (4) no-op. The NPC never attacks: soil, not
player.

Adventurer: (1) loot active at its position -> claim_loot; (2) combat
at its position last tick -> move to the adjacent neutral with fewest
units (tiebreak: lowest id); (3) no-op.

Pure function: no input mutation, no I/O, no randomness — the seed
parameter is part of the uniform phase signature but this policy is
deterministic without it.
"""

import copy

from engine.validate import ValidationError, validate_move


def _npc_force_order(state: dict, force_id: str, config) -> dict | None:
    regions = state["regions"]
    force = state["forces"][force_id]
    owned = sorted(rid for rid, r in regions.items() if r["owner"] == force_id)

    # (1) attacked last tick -> recruit 1 in the weakest own region
    attacked = any(
        rid in state["combats_last_tick"] for rid in owned
    )
    if attacked and force["essence"] >= config.economy.recruit_cost and owned:
        target = min(owned, key=lambda rid: (regions[rid]["units"], rid))
        return {"action": "recruit", "region": target, "count": 1}

    # (2) fortify own capital (frozen naming: capital-<n> <-> force-<n>)
    capital_id = "capital-" + force_id.removeprefix("force-")
    capital = regions.get(capital_id)
    if (
        force["essence"] >= config.economy.fortify_cost
        and capital is not None
        and capital["owner"] == force_id
        and capital["fortification"] < config.economy.fortify_cap
    ):
        return {"action": "fortify", "region": capital_id}

    # (3) expand: half of the strongest neutral-adjacent own region
    pairs = [
        (origin, dest)
        for origin in owned
        for dest in regions[origin]["adjacent"]
        if regions[dest]["owner"] is None
    ]
    if pairs:
        most_units = max(regions[origin]["units"] for origin, _ in pairs)
        origin, dest = min(
            (p for p in pairs if regions[p[0]]["units"] == most_units),
            key=lambda p: (p[1], p[0]),
        )
        count = regions[origin]["units"] // 2
        if count >= 1:
            return {"action": "move_units", "from": origin, "to": dest, "count": count}

    # (4) no-op
    return None


def _npc_adventurer_order(state: dict, adventurer_id: str) -> dict | None:
    regions = state["regions"]
    position = state["adventurers"][adventurer_id]["position"]

    # (1) loot underfoot
    if regions[position]["loot"] is not None:
        return {"action": "claim_loot", "region": position}

    # (2) flee last tick's combat to the weakest adjacent neutral
    if position in state["combats_last_tick"]:
        neutrals = [
            rid for rid in regions[position]["adjacent"]
            if regions[rid]["owner"] is None
        ]
        if neutrals:
            dest = min(neutrals, key=lambda rid: (regions[rid]["units"], rid))
            return {"action": "move_units", "from": position, "to": dest, "count": 1}

    # (3) no-op
    return None


def resolve_validation(state: dict, moves: list, config, seed: int) -> dict:
    """(state, moves, config, seed) -> phase-1 state delta.

    Returns a dict with:
      batches:         one effective batch per living actor, sorted by
                       actor id — submitted batches verbatim when valid,
                       NPC batches (origin npc, <= 1 order) otherwise
      substitutions:   [{actor, reason}] for every NPC replacement
      ignored_batches: [{actor, reason}] for batches no actor can own
    """
    expected_tick = state["tick"] + 1
    actors = sorted(list(state["forces"]) + list(state["adventurers"]))

    by_actor: dict[str, dict] = {}
    duplicates: set[str] = set()
    ignored: list[dict] = []
    for batch in moves:
        actor = batch.get("actor") if isinstance(batch, dict) else None
        if not isinstance(actor, str):
            ignored.append({"actor": None, "reason": "unparseable batch"})
        elif actor not in actors:
            ignored.append({"actor": actor, "reason": "unknown actor"})
        elif actor in by_actor:
            duplicates.add(actor)
        else:
            by_actor[actor] = batch

    batches: list[dict] = []
    substitutions: list[dict] = []
    for actor in actors:
        batch = by_actor.get(actor)
        reason = None
        if actor in duplicates:
            reason = "duplicate batches"
        elif batch is None:
            reason = "no batch submitted"
        else:
            try:
                validate_move(batch, config)
            except ValidationError:
                # stable summary, never a library-generated message:
                # delta bytes must not depend on the jsonschema version
                reason = "invalid batch (schema or cap violation)"
            else:
                if batch["tick"] != expected_tick:
                    reason = f"tick {batch['tick']} != expected {expected_tick}"

        if reason is None:
            batches.append(copy.deepcopy(batch))
            continue

        if actor.startswith("adventurer-"):
            order = _npc_adventurer_order(state, actor)
        else:
            order = _npc_force_order(state, actor, config)
        batches.append({
            "actor": actor,
            "tick": expected_tick,
            "origin": "npc",
            "orders": [order] if order is not None else [],
        })
        substitutions.append({"actor": actor, "reason": reason})

    return {
        "batches": batches,
        "substitutions": substitutions,
        "ignored_batches": ignored,
    }
