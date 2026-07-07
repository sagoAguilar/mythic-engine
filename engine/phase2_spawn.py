"""Phase 2 of the resolution order: ``spawn_adventurer``.

The only move with no prior entity (docs/intent.md). Free in v1: the new
entity gets baseline essence, initial reputation with every force, and
the era's personal quest — all from era.yml. One living entity per
username: the actor id ``adventurer-<handle>`` carries the identity, and
``controller: github:<handle>`` derives from it (the workflow validates
pr.author == handle before a move ever reaches the engine, so the engine
never needs PR metadata). Permadeath frees the username: a graveyard
record does not block a respawn.

Spawnable origins (micro-rubber-band): neutral regions, or the territory
of the force with strictly least dominance (fewest owned regions, unique
minimum). The strictness is pinned by M3: at tick 0 every force ties, no
strict minimum exists, and the spawnables are exactly the 9 neutrals.

Pure function: no input mutation, no I/O, no randomness — the seed
parameter is part of the uniform phase signature but spawning is
deterministic without it.
"""


def _strictly_least_dominant(state: dict) -> str | None:
    counts = {force_id: 0 for force_id in state["forces"]}
    for region in state["regions"].values():
        if region["owner"] in counts:
            counts[region["owner"]] += 1
    ranked = sorted(counts.values())
    if len(ranked) >= 2 and ranked[0] == ranked[1]:
        return None  # tie: no force is strictly behind
    return min(counts, key=counts.get)


def resolve_spawn(state: dict, moves: list[dict], config, seed: int) -> dict:
    """(state, moves, config, seed) -> phase-2 state delta.

    Returns a dict with:
      spawned:         {adventurer_id: entity} for every successful spawn,
                       entities conforming to the world-schema adventurer def
      rejected_orders: [{actor, index, reason}] for failed preconditions
    """
    regions = state["regions"]
    least_dominant = _strictly_least_dominant(state)

    spawned: dict[str, dict] = {}
    rejected: list[dict] = []

    def reject(actor: str, index: int, reason: str) -> None:
        rejected.append({"actor": actor, "index": index, "reason": reason})

    for batch in sorted(moves, key=lambda b: b["actor"]):
        actor = batch["actor"]
        for index, order in enumerate(batch["orders"]):
            if order.get("action") != "spawn_adventurer":
                continue
            if not actor.startswith("adventurer-"):
                reject(actor, index, "spawn_adventurer: only an adventurer actor may spawn")
                continue
            if actor in state["adventurers"] or actor in spawned:
                reject(actor, index, f"spawn_adventurer: {actor} already has a living entity")
                continue
            origin = order["origin"]
            region = regions.get(origin)
            if region is None:
                reject(actor, index, f"spawn_adventurer: unknown region {origin}")
                continue
            if region["owner"] is not None and region["owner"] != least_dominant:
                reject(actor, index,
                       f"spawn_adventurer: {origin} is not spawnable "
                       "(neutral or strictly least-dominant force territory only)")
                continue

            handle = actor.removeprefix("adventurer-")
            spawned[actor] = {
                "id": actor,
                "name": order["name"],
                "controller": f"github:{handle}",
                "essence": config.adventurer.baseline_essence,
                "position": origin,
                "units": 1,
                "reputation": {
                    force_id: config.reputation.initial
                    for force_id in sorted(state["forces"])
                },
                "capabilities": [],
                "personal_quest": {
                    "type": config.adventurer.personal_quest.type,
                    "target": config.adventurer.personal_quest.target,
                },
            }

    return {"spawned": dict(sorted(spawned.items())), "rejected_orders": rejected}
