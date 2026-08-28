"""Phase 6 of the resolution order: ``claim_loot`` and ``trade``.

``claim_loot`` (docs/intent.md catalog): adventurer-only, present in a
region with active loot — the position is the post-phase-4 one on the
working state, and loot is active while the resolving tick is at or
before its ``expires_tick`` ("reclamable por M ticks, luego se
disipa"; dissipation itself is not this phase's job). Effect: the
claimant gains the loot essence and the loot is extinguished.

When several eligible claimants stand on the same pot, the claim is
awarded by the same seeded formula that orders every collision:
``sha256(f"{seed}:{tick}:{region}:{actor}")`` — never by batch order
or actor-id ordinal. Later claimants are rejected with the pot gone.

``trade`` (F8, adventurer-only): trades essence for reputation with
whichever force owns the adventurer's current region — a hard, genuine
transfer (essence moves, it isn't destroyed), gated behind three
preconditions checked in order: the region must belong to a force (not
neutral), the adventurer's reputation with it must already meet
``reputation.thresholds.trade``, and their essence (drawn from the same
pre-tick pool ``recruit``/``fortify`` use) must cover
``adventurer.trade_cost``. Past those, the attempt always resolves —
never rejected for the probabilistic part — via a seeded roll
(``sha256(seed:tick:actor:force)`` against the region's structural
depth-tier success chance, ``adventurer.trade_success_pct``: ring is
riskiest, arm safer, capital guaranteed). On success the flat cost
transfers to the force and reputation rises by
``reputation.deltas.trade_per_tick`` (clamped to the era's reputation
scale, same discipline as phase 8's quest rewards). On failure: no
essence moves, no reputation changes — only the order slot was spent,
same principle as a lost F1 duel not being "rejected" either.

Pure function: no input mutation, no I/O, no wall clock — the seed
feeds both formulas above, never true randomness.
"""

import hashlib


def _claim_key(seed: int, tick: int, region: str, actor: str) -> str:
    return hashlib.sha256(f"{seed}:{tick}:{region}:{actor}".encode("utf-8")).hexdigest()


def _trade_roll(seed: int, tick: int, actor: str, force_id: str) -> int:
    """Deterministic 0..99 roll for one trade attempt (F8)."""
    digest = hashlib.sha256(f"{seed}:{tick}:{actor}:{force_id}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def _depth_tier(region_id: str) -> str:
    """Structural depth tier from the region's own id - independent of
    who currently owns it (capital-<i>, arm-<i>-{a,b}, ring-<i>)."""
    if region_id.startswith("capital-"):
        return "capital"
    if region_id.startswith("arm-"):
        return "arm"
    return "ring"


def resolve_claim_loot(state: dict, moves: list[dict], config, seed: int) -> dict:
    """(state, moves, config, seed) -> phase-6 state delta.

    Returns a dict with:
      essence_changes:     {actor: net essence delta} (loot gains, trade spend/income)
      reputation_changes:  {adventurer_id: {force_id: clamped delta}}
      loot_changes:         {region_id: None} for every extinguished pot
      loot_claims:           {adventurer_id: essence gained from loot alone} -
                              a loot-only view of essence_changes, for the chronicle
      trade_results:         [{actor, force, success}] every resolved trade attempt
      rejected_orders:       [{actor, index, reason}] for failed preconditions
    """
    tick = state["tick"] + 1
    regions = state["regions"]

    rejected: list[dict] = []
    # region -> [(actor, index)] eligible claimants awaiting the seeded award
    claimants: dict[str, list[tuple[str, int]]] = {}
    essence_changes: dict[str, int] = {}
    reputation_changes: dict[str, dict[str, int]] = {}
    trade_results: list[dict] = []

    def reject(actor: str, index: int, reason: str) -> None:
        rejected.append({"actor": actor, "index": index, "reason": reason})

    for batch in sorted(moves, key=lambda b: b["actor"]):
        actor = batch["actor"]
        for index, order in enumerate(batch["orders"]):
            action = order.get("action")
            if action not in ("claim_loot", "trade"):
                continue
            verb = "claim loot" if action == "claim_loot" else "trade"
            if not actor.startswith("adventurer-"):
                reject(actor, index, f"{action}: only an adventurer may {verb}")
                continue
            adventurer = state["adventurers"].get(actor)
            if adventurer is None:
                reject(actor, index, f"{action}: no living adventurer entity")
                continue
            region_id = order["region"]
            region = regions.get(region_id)
            if region is None:
                reject(actor, index, f"{action}: unknown region {region_id}")
                continue
            if adventurer["position"] != region_id:
                reject(actor, index, f"{action}: {actor} is not present in {region_id}")
                continue

            if action == "claim_loot":
                loot = region["loot"]
                if loot is None or loot["expires_tick"] < tick:
                    reject(actor, index, f"claim_loot: no active loot in {region_id}")
                    continue
                claimants.setdefault(region_id, []).append((actor, index))
                continue

            # trade
            force_id = region["owner"]
            if force_id is None:
                reject(actor, index, f"trade: {region_id} is not a force's territory")
                continue
            reputation = adventurer["reputation"][force_id]
            if reputation < config.reputation.thresholds.trade:
                reject(actor, index,
                       f"trade: {actor}'s reputation {reputation} with {force_id} is "
                       f"below the trade threshold {config.reputation.thresholds.trade}")
                continue
            cost = config.adventurer.trade_cost
            remaining = adventurer["essence"] + essence_changes.get(actor, 0)
            if cost > remaining:
                reject(actor, index,
                       f"trade: cost {cost} exceeds the {remaining} essence remaining for {actor}")
                continue

            success_pct = config.adventurer.trade_success_pct.for_tier(_depth_tier(region_id))
            success = _trade_roll(seed, tick, actor, force_id) < success_pct
            trade_results.append({"actor": actor, "force": force_id, "success": success})
            if not success:
                continue

            essence_changes[actor] = essence_changes.get(actor, 0) - cost
            essence_changes[force_id] = essence_changes.get(force_id, 0) + cost
            per_actor = reputation_changes.setdefault(actor, {})
            before = reputation + per_actor.get(force_id, 0)
            after = max(
                config.reputation.scale_min,
                min(config.reputation.scale_max, before + config.reputation.deltas.trade_per_tick),
            )
            per_actor[force_id] = per_actor.get(force_id, 0) + (after - before)

    loot_changes: dict[str, None] = {}
    loot_claims: dict[str, int] = {}
    for region_id in sorted(claimants):
        ordered = sorted(
            claimants[region_id],
            key=lambda claim: _claim_key(seed, tick, region_id, claim[0]),
        )
        winner, _ = ordered[0]
        pot = regions[region_id]["loot"]["essence"]
        essence_changes[winner] = essence_changes.get(winner, 0) + pot
        loot_claims[winner] = loot_claims.get(winner, 0) + pot
        loot_changes[region_id] = None
        for actor, index in ordered[1:]:
            reject(actor, index,
                   f"claim_loot: loot in {region_id} extinguished by an earlier claim")

    rejected.sort(key=lambda r: (r["actor"], r["index"]))
    return {
        "essence_changes": dict(sorted(essence_changes.items())),
        "reputation_changes": dict(sorted(reputation_changes.items())),
        "loot_changes": dict(sorted(loot_changes.items())),
        "loot_claims": dict(sorted(loot_claims.items())),
        "trade_results": trade_results,
        "rejected_orders": rejected,
    }
