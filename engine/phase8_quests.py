"""Phase 8 of the resolution order: quest objectives against post-combat state.

Two passes, strictly ordered:

1. **Verify** every active quest (sorted by id) against the post-combat
   working state, using the frozen catalog predicates:
     raid      - params.region no longer owned by params.force
     blockade  - claimant occupied params.region this tick (force owns it
                 or adventurer stands on it); streak in quest.progress
                 reaches params.n_ticks
     attrition - params.force fields <= units_at_spawn - delta units
                 (summed over its regions; the cached total is not trusted)
     dethrone  - supremacy streak of params.force is back to 0 (phase 10's
                 last written value)
   Deadlines are inclusive: fulfillable while tick <= deadline, expired
   after. Unclaimed quests never fulfill - they wait or expire. On
   success every claimant collects the quest's reward; an adventurer
   claimant also takes the reputation hit for damaging params.force
   (quest_damages_force with it, quest_damages_force_rivals with its
   rivals, clamped to the era scale). On failure the stake is already
   gone (charged at accept); an adventurer claimant sitting at zero
   essence dies - permadeath, graveyard, no deposit to loot.

2. **Accept** this tick's accept_quest orders - after verification, so a
   same-tick engineered fulfillment can never be instantly rewarded.
   Eligibility, liveness, quota, and stake affordability are checked;
   competing claims on limited slots are ordered by the seeded collision
   formula sha256(seed:tick:quest_id:actor), never by batch order or
   actor id. Stakes are charged on acceptance.

Pure function: no input mutation, no I/O, no wall clock.
"""

import hashlib


def _claim_key(seed: int, tick: int, quest_id: str, actor: str) -> str:
    return hashlib.sha256(f"{seed}:{tick}:{quest_id}:{actor}".encode("utf-8")).hexdigest()


def _force_units(state: dict, force_id: str) -> int:
    return sum(
        r["units"] for r in state["regions"].values() if r["owner"] == force_id
    )


def _occupies(state: dict, actor: str, region_id: str) -> bool:
    if actor.startswith("adventurer-"):
        adventurer = state["adventurers"].get(actor)
        return adventurer is not None and adventurer["position"] == region_id
    return state["regions"][region_id]["owner"] == actor


def resolve_quests(state: dict, moves: list[dict], config, seed: int) -> dict:
    """(state, moves, config, seed) -> phase-8 state delta.

    Returns a dict with:
      essence_changes:     {actor: rewards earned minus stakes charged}
      reputation_changes:  {adventurer_id: {force_id: clamped delta}}
      quest_progress:      {quest_id: new progress} for still-active quests
      quests_resolved:     {quest_id: "success" | "failure"}
      quest_claims:        {quest_id: new claimed_by list}
      adventurer_deaths:   [{id, region, killer: None}] zero-essence failures
      graveyard_additions: [full graveyard entries]
      rejected_orders:     [{actor, index, reason}]
    """
    tick = state["tick"] + 1
    active = state["quests"]["active"]

    essence_changes: dict[str, int] = {}
    reputation_changes: dict[str, dict[str, int]] = {}
    quest_progress: dict[str, dict[str, int]] = {}
    quests_resolved: dict[str, str] = {}
    quest_claims: dict[str, list[str]] = {}
    deaths: list[dict] = []
    graveyard_additions: list[dict] = []
    rejected: list[dict] = []

    def add_essence(actor: str, amount: int) -> None:
        essence_changes[actor] = essence_changes.get(actor, 0) + amount

    def current_essence(actor: str) -> int:
        pool = state["adventurers"] if actor.startswith("adventurer-") else state["forces"]
        return pool[actor]["essence"] + essence_changes.get(actor, 0)

    # --- pass 1: verify objectives ------------------------------------------
    for quest_id in sorted(active):
        quest = active[quest_id]
        claimants = quest["claimed_by"]
        fulfilled = False

        if claimants and tick <= quest["deadline"]:
            if quest["type"] == "raid":
                fulfilled = (
                    state["regions"][quest["params"]["region"]]["owner"]
                    != quest["params"]["force"]
                )
            elif quest["type"] == "blockade":
                streaks = {}
                for claimant in claimants:
                    streak = quest["progress"].get(claimant, 0)
                    streak = streak + 1 if _occupies(state, claimant, quest["params"]["region"]) else 0
                    streaks[claimant] = streak
                fulfilled = any(s >= quest["params"]["n_ticks"] for s in streaks.values())
                if not fulfilled:
                    quest_progress[quest_id] = streaks
            elif quest["type"] == "attrition":
                fulfilled = _force_units(state, quest["params"]["force"]) <= (
                    quest["params"]["units_at_spawn"] - quest["params"]["delta"]
                )
            elif quest["type"] == "dethrone":
                fulfilled = state["supremacy"]["streaks"].get(quest["params"]["force"], 0) == 0

        if fulfilled:
            quests_resolved[quest_id] = "success"
            quest_progress.pop(quest_id, None)
            damaged = quest["params"].get("force")
            for claimant in claimants:
                add_essence(claimant, quest["reward"])
                if claimant.startswith("adventurer-") and damaged is not None:
                    reputation = state["adventurers"][claimant]["reputation"]
                    pending = reputation_changes.setdefault(claimant, {})
                    for force_id in sorted(state["forces"]):
                        delta = (
                            config.reputation.deltas.quest_damages_force
                            if force_id == damaged
                            else config.reputation.deltas.quest_damages_force_rivals
                        )
                        current = reputation[force_id] + pending.get(force_id, 0)
                        clamped = max(
                            config.reputation.scale_min,
                            min(config.reputation.scale_max, current + delta),
                        )
                        pending[force_id] = pending.get(force_id, 0) + clamped - current
        elif tick > quest["deadline"]:
            quests_resolved[quest_id] = "failure"
            quest_progress.pop(quest_id, None)
            for claimant in claimants:
                if claimant.startswith("adventurer-"):
                    adventurer = state["adventurers"].get(claimant)
                    if adventurer is not None and current_essence(claimant) == 0:
                        deaths.append({
                            "id": claimant,
                            "region": adventurer["position"],
                            "killer": None,
                        })
                        graveyard_additions.append({
                            "id": claimant,
                            "name": adventurer["name"],
                            "controller": adventurer["controller"],
                            "died_tick": tick,
                            "era": config.era.number,
                            "titles": [],
                        })

    # --- pass 2: acceptances -------------------------------------------------
    dead_ids = {d["id"] for d in deaths}
    # quest_id -> [(actor, index)] surviving the static checks
    requests: dict[str, list[tuple[str, int]]] = {}

    def reject(actor: str, index: int, reason: str) -> None:
        rejected.append({"actor": actor, "index": index, "reason": reason})

    for batch in sorted(moves, key=lambda b: b["actor"]):
        actor = batch["actor"]
        for index, order in enumerate(batch["orders"]):
            if order.get("action") != "accept_quest":
                continue
            quest_id = order["quest_id"]
            quest = active.get(quest_id)
            is_adventurer = actor.startswith("adventurer-")
            if quest is None or quest_id in quests_resolved:
                reject(actor, index, f"accept_quest: {quest_id} is not an active quest")
                continue
            if is_adventurer and (actor not in state["adventurers"] or actor in dead_ids):
                reject(actor, index, "accept_quest: no living adventurer entity")
                continue
            if not is_adventurer and actor not in state["forces"]:
                reject(actor, index, f"accept_quest: unknown force {actor}")
                continue
            eligibility = quest["eligibility"]
            if eligibility == "forces" and is_adventurer:
                reject(actor, index, f"accept_quest: {quest_id} eligibility is forces")
                continue
            if eligibility == "adventurer" and not is_adventurer:
                reject(actor, index, f"accept_quest: {quest_id} eligibility is adventurer")
                continue
            if actor in quest["claimed_by"]:
                reject(actor, index, f"accept_quest: already a claimant of {quest_id}")
                continue
            if quest["max_claimants"] != "open" and len(quest["claimed_by"]) >= quest["max_claimants"]:
                reject(actor, index, f"accept_quest: {quest_id} quota is full")
                continue
            requests.setdefault(quest_id, []).append((actor, index))

    for quest_id in sorted(requests):
        quest = active[quest_id]
        slots = (
            None if quest["max_claimants"] == "open"
            else quest["max_claimants"] - len(quest["claimed_by"])
        )
        ordered = sorted(
            requests[quest_id], key=lambda req: _claim_key(seed, tick, quest_id, req[0])
        )
        accepted: list[str] = []
        for actor, index in ordered:
            if slots is not None and len(accepted) >= slots:
                reject(actor, index,
                       f"accept_quest: {quest_id} quota filled by seeded order")
                continue
            if current_essence(actor) < quest["stake"]:
                reject(actor, index,
                       f"accept_quest: stake {quest['stake']} exceeds "
                       f"{actor}'s {current_essence(actor)} essence")
                continue
            add_essence(actor, -quest["stake"])
            accepted.append(actor)
        if accepted:
            quest_claims[quest_id] = quest["claimed_by"] + accepted

    rejected.sort(key=lambda r: (r["actor"], r["index"]))
    return {
        "essence_changes": dict(sorted(essence_changes.items())),
        "reputation_changes": {
            aid: dict(sorted(by_force.items()))
            for aid, by_force in sorted(reputation_changes.items())
        },
        "quest_progress": dict(sorted(quest_progress.items())),
        "quests_resolved": dict(sorted(quests_resolved.items())),
        "quest_claims": dict(sorted(quest_claims.items())),
        "adventurer_deaths": deaths,
        "graveyard_additions": graveyard_additions,
        "rejected_orders": rejected,
    }
