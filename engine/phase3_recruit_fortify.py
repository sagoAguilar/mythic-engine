"""Phase 3 of the resolution order: ``recruit``, ``fortify``, ``decree``.

All three spend the essence a force held at the start of the tick
(docs/intent.md: "esencia pre-tick") — phase-7 yield can never fund
same-tick orders. Within a batch, orders draw on the pool sequentially
in file order; an order the remaining pool cannot cover is rejected
whole (the catalog defines no partial fills).

Catalog preconditions enforced here: the region is owned by the acting
force; recruit costs ``count * recruit_cost``; fortify costs
``fortify_cost.at_level(current_level)`` — escalating, not flat, so
reaching level 3 costs strictly more than level 1 — adds one persistent
fortification level, and respects the fortification cap. All three
actions (recruit, fortify, decree) are force-only.

``decree`` (F7) is a category, not a single action:
``kind: dismiss`` removes ``count`` units from a region the force owns,
no essence change and no refund — the release valve for F5/F6's upkeep
pressure. ``kind: surge_recruit`` shares recruit's preconditions but
delivers ``2 * count`` units for the same per-unit cost; what it really
costs extra is a flat ``economy.decree_surge_surcharge`` on top, keyed
to the force's consecutive-tick streak of using it (capped at the 3rd
tier — it never doubles past that). Every force in ``surge_streak``
gets an explicit new value each tick: incremented (capped at 3) for a
force that successfully used surge_recruit at least once this tick —
every surge_recruit order from that force this same tick shares that
one streak value, it doesn't escalate again mid-tick — and reset to 0
for every other force whose streak wasn't already 0.

Pure function: no input mutation, no I/O, no randomness — the seed
parameter is part of the uniform phase signature but this phase is
deterministic without it.
"""


def resolve_recruit_fortify(state: dict, moves: list[dict], config, seed: int) -> dict:
    """(state, moves, config, seed) -> phase-3 state delta.

    Returns a dict with:
      essence_changes:       {force_id: negative essence spent}
      unit_changes:          {region_id: net units recruited/surged/dismissed}
      fortification_changes: {region_id: levels added}
      surge_streak_changes:  {force_id: new surge_streak value} for every
                              force whose streak differs from its current one
      rejected_orders:       [{actor, index, reason}] for failed preconditions

    Cached per-force unit totals are the resolver's to recompute when it
    assembles the next state; this delta stays minimal.
    """
    regions = state["regions"]

    essence_changes: dict[str, int] = {}
    unit_changes: dict[str, int] = {}
    fortification_changes: dict[str, int] = {}
    rejected: list[dict] = []

    surge_streak_this_tick: dict[str, int] = {}
    surge_succeeded: set[str] = set()

    def reject(actor: str, index: int, reason: str) -> None:
        rejected.append({"actor": actor, "index": index, "reason": reason})

    for batch in sorted(moves, key=lambda b: b["actor"]):
        actor = batch["actor"]
        for index, order in enumerate(batch["orders"]):
            action = order.get("action")
            if action not in ("recruit", "fortify", "decree"):
                continue
            if actor not in state["forces"]:
                verb = "issue a decree" if action == "decree" else "recruit or fortify"
                reject(actor, index, f"{action}: only a force may {verb}")
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
            elif action == "fortify":
                level = region["fortification"] + fortification_changes.get(region_id, 0)
                if level >= config.economy.fortify_cap:
                    reject(actor, index,
                           f"fortify: {region_id} is already at fortification "
                           f"cap {config.economy.fortify_cap}")
                    continue
                cost = config.economy.fortify_cost.at_level(level)
                if cost > remaining:
                    reject(actor, index,
                           f"fortify: cost {cost} exceeds the {remaining} "
                           f"essence remaining for {actor}")
                    continue
                essence_changes[actor] = essence_changes.get(actor, 0) - cost
                fortification_changes[region_id] = (
                    fortification_changes.get(region_id, 0) + 1
                )
            elif order["kind"] == "dismiss":
                available = region["units"] + unit_changes.get(region_id, 0)
                if order["count"] > available:
                    reject(actor, index,
                           f"decree: dismiss count {order['count']} exceeds the "
                           f"{available} units available in {region_id}")
                    continue
                unit_changes[region_id] = unit_changes.get(region_id, 0) - order["count"]
            else:  # surge_recruit
                if actor not in surge_streak_this_tick:
                    prior = state["forces"][actor]["surge_streak"]
                    surge_streak_this_tick[actor] = min(prior + 1, 3)
                surcharge = config.economy.decree_surge_surcharge.at_streak(
                    surge_streak_this_tick[actor]
                )
                cost = order["count"] * config.economy.recruit_cost + surcharge
                if cost > remaining:
                    reject(actor, index,
                           f"decree: surge_recruit cost {cost} exceeds the "
                           f"{remaining} essence remaining for {actor}")
                    continue
                essence_changes[actor] = essence_changes.get(actor, 0) - cost
                unit_changes[region_id] = (
                    unit_changes.get(region_id, 0) + order["count"] * 2
                )
                surge_succeeded.add(actor)

    surge_streak_changes: dict[str, int] = {}
    for force_id, force in state["forces"].items():
        if force_id in surge_succeeded:
            surge_streak_changes[force_id] = surge_streak_this_tick[force_id]
        elif force["surge_streak"] != 0:
            surge_streak_changes[force_id] = 0

    return {
        "essence_changes": dict(sorted(essence_changes.items())),
        "unit_changes": dict(sorted(unit_changes.items())),
        "fortification_changes": dict(sorted(fortification_changes.items())),
        "surge_streak_changes": dict(sorted(surge_streak_changes.items())),
        "rejected_orders": rejected,
    }
