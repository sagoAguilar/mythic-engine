"""Phase 4 of the resolution order: simultaneous movements and attacks.

Executes every valid ``move_units`` / ``attack_region`` order as a
simultaneous commitment (Diplomacy model, docs/intent.md):

- all departures leave their origin regions at once, so units committed
  to an attack do not defend (F2 mirror rule falls out of this);
- uncontested moves complete: reinforcements join own regions, a sole
  force arriving at a neutral region captures it;
- every attack, and every neutral region receiving movers from more than
  one force, becomes a pending combat for phase 5 — this phase stages
  combats but performs no combat math (F1 belongs to phase 5);
- parties within a contested region are ordered by
  ``sha256(f"{seed}:{tick}:{region}:{actor}")`` per F2 — never by PR
  order or force-id ordinal;
- the adventurer is a non-combatant (F4): moves to any adjacent region,
  coexists with any garrison, never collides. Killing it requires the
  explicit ``target: adventurer`` attack, staged here for phase 5.

``siege`` (F6, force-only) shares this phase's ``from``/available-units
bookkeeping but is not a movement or an attack: no F1 duel, no pending
combat. It commits ``count`` units out of the garrison economy entirely
(returned only when the siege later ends, in phase 7) against a hostile,
fortified ``to`` that isn't already under another siege — declared once,
staged here as ``sieges_started`` for the resolver to fold into the
persistent ``/world/sieges/`` state after this tick's phase 7 has run
(a fresh siege never erodes or pays upkeep on its own declare-tick).

Two guild capabilities also resolve here (docs/intent.md punto 9):

- ``swift_march`` (Bronze): the adventurer moves up to
  ``swift_march_hops`` adjacent hops in one order, each hop with
  ``move_units`` legality (adjacency; F4 coexistence means any owner is
  legal). Only the final position matters — the intermediate is
  irrelevant to output — so we verify reachability, not a path. Flat
  essence cost, charged once on success (phase 4).
- ``sanctuary`` (Silver): the adventurer sets
  ``sanctuary_until = tick + sanctuary_ticks - 1``, buying hunt immunity
  respected by phase 5. Flat essence cost, charged on success.

Both are adventurer-only, cost essence, and share the ``move_units``
one-move-per-tick budget (``sanctuary`` is not a move and has its own
guard). A failed precondition rejects the order uncharged.

Pure function: no input mutation, no I/O, no wall clock; the only
randomness is the seed chain above. Orders that fail their catalog
preconditions are reported in ``rejected_orders``, never applied.
"""

import hashlib


def _party_key(seed: int, tick: int, region: str, actor: str) -> str:
    return hashlib.sha256(f"{seed}:{tick}:{region}:{actor}".encode("utf-8")).hexdigest()


def _living_adventurer_at(state: dict, region: str) -> bool:
    return any(a["position"] == region for a in state["adventurers"].values())


def _reachable_within(regions: dict, src: str, max_hops: int) -> set[str]:
    """Regions reachable from *src* in 1..max_hops adjacent hops (F4
    coexistence: any owner is traversable). Excludes *src* itself."""
    frontier = {src}
    reached: set[str] = set()
    for _ in range(max_hops):
        nxt: set[str] = set()
        for region_id in frontier:
            for neighbour in regions[region_id]["adjacent"]:
                if neighbour not in reached and neighbour != src:
                    nxt.add(neighbour)
        reached |= nxt
        frontier = nxt
    return reached


def resolve_movement(state: dict, moves: list[dict], config, seed: int) -> dict:
    """(state, moves, config, seed) -> phase-4 state delta.

    Returns a dict with:
      unit_changes:     {region_id: net unit delta} (departures + settled arrivals)
      owner_changes:    {region_id: new owner} (neutral captures)
      adventurer_moves: {adventurer_id: new position}
      essence_changes:  {adventurer_id: net essence delta} (capability costs)
      sanctuary_until:  {adventurer_id: tick through which hunt-immune}
      pending_combats:  [{region, parties: [{actor, count, kind, target}]}]
                        parties ordered by the seeded formula, combats by region id
      sieges_started:   {region_id: {attacker, defender, from, units, ticks_elapsed: 0}}
      rejected_orders:  [{actor, index, reason}] for failed preconditions
    """
    tick = state["tick"] + 1
    regions = state["regions"]
    existing_sieges = state.get("sieges", {})

    unit_changes: dict[str, int] = {}
    owner_changes: dict[str, str] = {}
    adventurer_moves: dict[str, str] = {}
    essence_changes: dict[str, int] = {}
    sanctuary_until: dict[str, int] = {}
    sieges_started: dict[str, dict] = {}
    rejected: list[dict] = []
    # region -> actor -> {"count": int, "kind": str, "target": str | None}
    arrivals: dict[str, dict[str, dict]] = {}
    # (actor, region) -> units still available after prior commitments
    available: dict[tuple[str, str], int] = {}
    moved_adventurers: set[str] = set()
    sanctuaried: set[str] = set()
    # adventurer -> essence still available after prior capability charges
    adv_essence: dict[str, int] = {}
    costs = config.guild.capabilities.costs

    def reject(actor: str, index: int, reason: str) -> None:
        rejected.append({"actor": actor, "index": index, "reason": reason})

    def charge(region_id: str, delta: int) -> None:
        unit_changes[region_id] = unit_changes.get(region_id, 0) + delta

    def spend_essence(adventurer_id: str, amount: int) -> None:
        adv_essence[adventurer_id] -= amount
        essence_changes[adventurer_id] = essence_changes.get(adventurer_id, 0) - amount

    for batch in sorted(moves, key=lambda b: b["actor"]):
        actor = batch["actor"]
        is_adventurer = actor.startswith("adventurer-")
        for index, order in enumerate(batch["orders"]):
            action = order.get("action")

            if action == "sanctuary":
                if not is_adventurer:
                    reject(actor, index, "sanctuary: adventurer-only action")
                    continue
                adventurer = state["adventurers"].get(actor)
                if adventurer is None:
                    reject(actor, index, "sanctuary: no living adventurer entity")
                    continue
                if "sanctuary" not in adventurer["capabilities"]:
                    reject(actor, index, "sanctuary: capability not unlocked")
                    continue
                if actor in sanctuaried:
                    reject(actor, index, "sanctuary: already invoked this tick")
                    continue
                available_essence = adv_essence.setdefault(actor, adventurer["essence"])
                if available_essence < costs.sanctuary:
                    reject(actor, index,
                           f"sanctuary: {costs.sanctuary} essence exceeds the "
                           f"{available_essence} available")
                    continue
                spend_essence(actor, costs.sanctuary)
                sanctuaried.add(actor)
                sanctuary_until[actor] = (
                    tick + config.guild.capabilities.sanctuary_ticks - 1
                )
                continue

            if action == "swift_march":
                if not is_adventurer:
                    reject(actor, index, "swift_march: adventurer-only action")
                    continue
                adventurer = state["adventurers"].get(actor)
                if adventurer is None:
                    reject(actor, index, "swift_march: no living adventurer entity")
                    continue
                if "swift_march" not in adventurer["capabilities"]:
                    reject(actor, index, "swift_march: capability not unlocked")
                    continue
                if actor in moved_adventurers:
                    reject(actor, index, "swift_march: adventurer already moved this tick")
                    continue
                src_id, dst_id = order["from"], order["to"]
                if adventurer["position"] != src_id:
                    reject(actor, index, f"swift_march: adventurer is not in {src_id}")
                    continue
                if order["count"] != 1:
                    reject(actor, index, "swift_march: adventurer moves exactly 1 unit (itself)")
                    continue
                available_essence = adv_essence.setdefault(actor, adventurer["essence"])
                if available_essence < costs.swift_march:
                    reject(actor, index,
                           f"swift_march: {costs.swift_march} essence exceeds the "
                           f"{available_essence} available")
                    continue
                hops = config.guild.capabilities.swift_march_hops
                if dst_id not in _reachable_within(regions, src_id, hops):
                    reject(actor, index,
                           f"swift_march: {dst_id} is not reachable from {src_id} "
                           f"within {hops} hops")
                    continue
                spend_essence(actor, costs.swift_march)
                adventurer_moves[actor] = dst_id
                moved_adventurers.add(actor)
                continue

            if action == "siege":
                if is_adventurer:
                    reject(actor, index, "siege: adventurer cannot siege (force-only action)")
                    continue
                src_id, dst_id, count = order["from"], order["to"], order["count"]
                src = regions.get(src_id)
                if src is None or src["owner"] != actor:
                    reject(actor, index, f"siege: {src_id} is not owned by {actor}")
                    continue
                remaining = available.setdefault((actor, src_id), src["units"])
                if count > remaining:
                    reject(actor, index,
                           f"siege: {count} units exceed the {remaining} available in {src_id}")
                    continue
                dst = regions.get(dst_id)
                if dst is None or dst_id not in src["adjacent"]:
                    reject(actor, index, f"siege: {dst_id} is not adjacent to {src_id}")
                    continue
                if dst["owner"] is None or dst["owner"] == actor:
                    reject(actor, index, f"siege: {dst_id} is not hostile to {actor}")
                    continue
                if dst["fortification"] <= 0:
                    reject(actor, index, f"siege: {dst_id} has no fortification to erode")
                    continue
                if dst_id in existing_sieges or dst_id in sieges_started:
                    reject(actor, index, f"siege: {dst_id} is already under siege")
                    continue
                available[(actor, src_id)] = remaining - count
                charge(src_id, -count)
                sieges_started[dst_id] = {
                    "attacker": actor,
                    "defender": dst["owner"],
                    "from": src_id,
                    "units": count,
                    "ticks_elapsed": 0,
                }
                continue

            if action not in ("move_units", "attack_region"):
                continue

            if is_adventurer:
                if action == "attack_region":
                    reject(actor, index, "attack_region: adventurer cannot attack (force-only action)")
                    continue
                adventurer = state["adventurers"].get(actor)
                if adventurer is None:
                    reject(actor, index, "move_units: no living adventurer entity")
                    continue
                if actor in moved_adventurers:
                    reject(actor, index, "move_units: adventurer already moved this tick")
                    continue
                src_id, dst_id = order["from"], order["to"]
                if adventurer["position"] != src_id:
                    reject(actor, index, f"move_units: adventurer is not in {src_id}")
                    continue
                if order["count"] != 1:
                    reject(actor, index, "move_units: adventurer moves exactly 1 unit (itself)")
                    continue
                if dst_id not in regions or dst_id not in regions[src_id]["adjacent"]:
                    reject(actor, index, f"move_units: {dst_id} is not adjacent to {src_id}")
                    continue
                # F4 coexistence: any owner is a legal destination
                adventurer_moves[actor] = dst_id
                moved_adventurers.add(actor)
                continue

            src_id, dst_id, count = order["from"], order["to"], order["count"]
            src = regions.get(src_id)
            if src is None or src["owner"] != actor:
                reject(actor, index, f"{action}: {src_id} is not owned by {actor}")
                continue
            remaining = available.setdefault((actor, src_id), src["units"])
            if count > remaining:
                reject(actor, index,
                       f"{action}: {count} units exceed the {remaining} available in {src_id}")
                continue
            dst = regions.get(dst_id)
            if dst is None or dst_id not in src["adjacent"]:
                reject(actor, index, f"{action}: {dst_id} is not adjacent to {src_id}")
                continue

            target = order.get("target")
            if action == "move_units":
                if dst["owner"] is not None and dst["owner"] != actor:
                    reject(actor, index,
                           f"move_units: {dst_id} is hostile; use attack_region")
                    continue
            elif target == "adventurer":
                if not _living_adventurer_at(state, dst_id):
                    reject(actor, index,
                           f"attack_region: no adventurer present in {dst_id}")
                    continue
            elif dst["owner"] is None or dst["owner"] == actor:
                reject(actor, index,
                       f"attack_region: {dst_id} is not hostile to {actor}")
                continue

            available[(actor, src_id)] = remaining - count
            charge(src_id, -count)
            kind = "move" if action == "move_units" else "attack"
            entry = arrivals.setdefault(dst_id, {}).setdefault(
                actor, {"count": 0, "kind": kind, "target": None}
            )
            entry["count"] += count
            entry["kind"] = kind
            if target == "adventurer":
                entry["target"] = "adventurer"

    pending_combats: list[dict] = []
    for region_id in sorted(arrivals):
        region = regions[region_id]
        parties: dict[str, dict] = {}
        for actor, entry in arrivals[region_id].items():
            if entry["kind"] == "move" and region["owner"] == actor:
                charge(region_id, entry["count"])  # reinforcement always lands
            else:
                parties[actor] = entry
        if not parties:
            continue
        movers_only = all(e["kind"] == "move" for e in parties.values())
        if movers_only and len(parties) == 1:
            # sole force arriving at a neutral region: occupation captures
            actor, entry = next(iter(parties.items()))
            charge(region_id, entry["count"])
            if region["owner"] is None:
                owner_changes[region_id] = actor
            continue
        ordered = sorted(parties, key=lambda a: _party_key(seed, tick, region_id, a))
        pending_combats.append({
            "region": region_id,
            "parties": [
                {"actor": actor,
                 "count": parties[actor]["count"],
                 "kind": parties[actor]["kind"],
                 "target": parties[actor]["target"]}
                for actor in ordered
            ],
        })

    return {
        "unit_changes": {k: v for k, v in sorted(unit_changes.items()) if v != 0},
        "owner_changes": dict(sorted(owner_changes.items())),
        "adventurer_moves": dict(sorted(adventurer_moves.items())),
        "essence_changes": {k: v for k, v in sorted(essence_changes.items()) if v != 0},
        "sanctuary_until": dict(sorted(sanctuary_until.items())),
        "pending_combats": pending_combats,
        "sieges_started": dict(sorted(sieges_started.items())),
        "rejected_orders": rejected,
    }
