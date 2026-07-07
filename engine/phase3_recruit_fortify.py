"""Phase 3 of the resolution order: ``recruit`` and ``fortify``.

Both actions spend the essence a force held at the start of the tick
(docs/intent.md: "esencia pre-tick") — phase-7 yield can never fund
same-tick orders. Within a batch, orders draw on the pool sequentially
in file order; an order the remaining pool cannot cover is rejected
whole (the catalog defines no partial fills).

Catalog preconditions enforced here: the region is owned by the acting
force; recruit costs ``count * recruit_cost``; fortify costs
``fortify_cost``, adds one persistent fortification level, and respects
the fortification cap — all values from era.yml. Both actions are
force-only.

Pure function: no input mutation, no I/O, no randomness — the seed
parameter is part of the uniform phase signature but this phase is
deterministic without it.
"""


def resolve_recruit_fortify(state: dict, moves: list[dict], config, seed: int) -> dict:
    """(state, moves, config, seed) -> phase-3 state delta.

    Returns a dict with:
      essence_changes:       {force_id: negative essence spent}
      unit_changes:          {region_id: units recruited}
      fortification_changes: {region_id: levels added}
      rejected_orders:       [{actor, index, reason}] for failed preconditions

    Cached per-force unit totals are the resolver's to recompute when it
    assembles the next state; this delta stays minimal.
    """
    regions = state["regions"]

    essence_changes: dict[str, int] = {}
    unit_changes: dict[str, int] = {}
    fortification_changes: dict[str, int] = {}
    rejected: list[dict] = []

    def reject(actor: str, index: int, reason: str) -> None:
        rejected.append({"actor": actor, "index": index, "reason": reason})

    for batch in sorted(moves, key=lambda b: b["actor"]):
        actor = batch["actor"]
        for index, order in enumerate(batch["orders"]):
            action = order.get("action")
            if action not in ("recruit", "fortify"):
                continue
            if actor not in state["forces"]:
                reject(actor, index, f"{action}: only a force may recruit or fortify")
                continue

            region_id = order["region"]
            region = regions.get(region_id)
            if region is None:
                reject(actor, index, f"{action}: unknown region {region_id}")
                continue
            if region["owner"] != actor:
                reject(actor, index, f"{action}: {region_id} is not owned by {actor}")
                continue

            remaining = state["forces"][actor]["essence"] + essence_changes.get(actor, 0)
            if action == "recruit":
                cost = order["count"] * config.economy.recruit_cost
                if cost > remaining:
                    reject(actor, index,
                           f"recruit: cost {cost} exceeds the {remaining} "
                           f"essence remaining for {actor}")
                    continue
                essence_changes[actor] = essence_changes.get(actor, 0) - cost
                unit_changes[region_id] = unit_changes.get(region_id, 0) + order["count"]
            else:
                level = region["fortification"] + fortification_changes.get(region_id, 0)
                if level >= config.economy.fortify_cap:
                    reject(actor, index,
                           f"fortify: {region_id} is already at fortification "
                           f"cap {config.economy.fortify_cap}")
                    continue
                cost = config.economy.fortify_cost
                if cost > remaining:
                    reject(actor, index,
                           f"fortify: cost {cost} exceeds the {remaining} "
                           f"essence remaining for {actor}")
                    continue
                essence_changes[actor] = essence_changes.get(actor, 0) - cost
                fortification_changes[region_id] = (
                    fortification_changes.get(region_id, 0) + 1
                )

    return {
        "essence_changes": dict(sorted(essence_changes.items())),
        "unit_changes": dict(sorted(unit_changes.items())),
        "fortification_changes": dict(sorted(fortification_changes.items())),
        "rejected_orders": rejected,
    }
