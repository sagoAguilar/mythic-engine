"""Phase 6 of the resolution order: ``claim_loot``.

Adventurer-only (docs/intent.md catalog). Precondition: present in a
region with active loot — the position is the post-phase-4 one on the
working state, and loot is active while the resolving tick is at or
before its ``expires_tick`` ("reclamable por M ticks, luego se
disipa"; dissipation itself is not this phase's job). Effect: the
claimant gains the loot essence and the loot is extinguished.

When several eligible claimants stand on the same pot, the claim is
awarded by the same seeded formula that orders every collision:
``sha256(f"{seed}:{tick}:{region}:{actor}")`` — never by batch order
or actor-id ordinal. Later claimants are rejected with the pot gone.

Pure function: no input mutation, no I/O, no wall clock.
"""

import hashlib


def _claim_key(seed: int, tick: int, region: str, actor: str) -> str:
    return hashlib.sha256(f"{seed}:{tick}:{region}:{actor}".encode("utf-8")).hexdigest()


def resolve_claim_loot(state: dict, moves: list[dict], config, seed: int) -> dict:
    """(state, moves, config, seed) -> phase-6 state delta.

    Returns a dict with:
      essence_changes: {adventurer_id: essence gained}
      loot_changes:    {region_id: None} for every extinguished pot
      rejected_orders: [{actor, index, reason}] for failed preconditions
    """
    tick = state["tick"] + 1
    regions = state["regions"]

    rejected: list[dict] = []
    # region -> [(actor, index)] eligible claimants awaiting the seeded award
    claimants: dict[str, list[tuple[str, int]]] = {}

    def reject(actor: str, index: int, reason: str) -> None:
        rejected.append({"actor": actor, "index": index, "reason": reason})

    for batch in sorted(moves, key=lambda b: b["actor"]):
        actor = batch["actor"]
        for index, order in enumerate(batch["orders"]):
            if order.get("action") != "claim_loot":
                continue
            if not actor.startswith("adventurer-"):
                reject(actor, index, "claim_loot: only an adventurer may claim loot")
                continue
            adventurer = state["adventurers"].get(actor)
            if adventurer is None:
                reject(actor, index, "claim_loot: no living adventurer entity")
                continue
            region_id = order["region"]
            region = regions.get(region_id)
            if region is None:
                reject(actor, index, f"claim_loot: unknown region {region_id}")
                continue
            if adventurer["position"] != region_id:
                reject(actor, index, f"claim_loot: {actor} is not present in {region_id}")
                continue
            loot = region["loot"]
            if loot is None or loot["expires_tick"] < tick:
                reject(actor, index, f"claim_loot: no active loot in {region_id}")
                continue
            claimants.setdefault(region_id, []).append((actor, index))

    essence_changes: dict[str, int] = {}
    loot_changes: dict[str, None] = {}
    for region_id in sorted(claimants):
        ordered = sorted(
            claimants[region_id],
            key=lambda claim: _claim_key(seed, tick, region_id, claim[0]),
        )
        winner, _ = ordered[0]
        pot = regions[region_id]["loot"]["essence"]
        essence_changes[winner] = essence_changes.get(winner, 0) + pot
        loot_changes[region_id] = None
        for actor, index in ordered[1:]:
            reject(actor, index,
                   f"claim_loot: loot in {region_id} extinguished by an earlier claim")

    rejected.sort(key=lambda r: (r["actor"], r["index"]))
    return {
        "essence_changes": dict(sorted(essence_changes.items())),
        "loot_changes": dict(sorted(loot_changes.items())),
        "rejected_orders": rejected,
    }
