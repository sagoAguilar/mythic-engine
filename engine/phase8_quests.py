"""Phase 8 of the resolution order: quest objectives against post-combat state.

Three passes, strictly ordered:

0. **Apply guild markers** - the `insure`/`entrench`/`wager` capability
   actions (sorted by actor, then order index). Each marks a guild quest the
   adventurer has claimed and charges its capability cost; the marker is
   idempotent (re-invoking an already-marked quest is rejected, uncharged).
     insure   - refunds quest.stake if the quest later fails/expires
     entrench - hold only: +1 progress to the claimant's streak this tick
                (equiv. -1 tick); the marker only guards the once-per-quest
                rule, the bonus is not re-added on later ticks
     wager    - success doubles the essence reward only (reputation intact);
                a Bronze coin miss under wager pays 0 (the forfeited
                consolation is the "nada" of double-or-nothing)
   Markers persist into quest.params so a later tick sees them.

1. **Verify** every active quest (sorted by id) against the post-combat
   working state, using the frozen catalog predicates:
     raid      - params.region no longer owned by params.force
     blockade  - claimant occupied params.region this tick (force owns it
                 or adventurer stands on it); streak in quest.progress
                 reaches params.n_ticks
     hold      - the guild twin of blockade: adventurer holds params.region
                 for params.n_ticks consecutive ticks (same streak logic)
     travel    - a claimant stands on params.region this tick (reached at
                 some tick <= deadline; no route restriction in v1)
     attrition - params.force fields <= units_at_spawn - delta units
                 (summed over its regions; the cached total is not trusted)
     dethrone  - supremacy streak of params.force is back to 0 (phase 10's
                 last written value)
   Deadlines are inclusive: fulfillable while tick <= deadline, expired
   after. Unclaimed quests never fulfill - they wait or expire.

   On success the reward path forks on whether the quest is a guild board
   (params.guild_tier present):
     - Guild board: the adventurer allies with params.force - positive
       reputation with that force alone (no rivals, no damage). Bronze pays
       via a seeded coin-flip sha256(seed:tick:adventurer:quest_id), even ->
       hit (+bronze_hit essence, +bronze reputation), odd -> miss
       (+bronze_miss essence, +0 reputation); Silver/Gold/Platinum pay flat
       essence and reputation. A `wagered` board doubles the essence only
       (reputation untouched; a Bronze miss under wager pays 0). Completing a
       tier records it (a Bronze miss still completes) and confers its
       capability: Bronze/Silver the shared pair, Gold the board force's
       signature, Platinum nothing in v1.
     - Damage quest: every claimant collects quest.reward; an adventurer
       claimant also takes the reputation hit for damaging params.force
       (quest_damages_force with it, quest_damages_force_rivals with its
       rivals).
   All reputation deltas clamp to the era scale. On failure the stake is
   already gone (charged at accept) unless the board was `insured`, which
   refunds it - and the refund lands before the zero-essence check, so it can
   save the adventurer. An adventurer claimant still sitting at zero essence
   dies - permadeath, graveyard, no deposit to loot. A failed guild board
   levies no reputation penalty (only the unrefunded stake).

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


def _tier_capability(config, tier: str, force_id: str) -> str | None:
    """The capability a completed guild tier grants, or None.

    Bronze/Silver grant the shared capabilities; Gold grants the board
    force's signature; Platinum grants nothing in v1 (the comodín is
    deferred - see docs/intent.md).
    """
    caps = config.guild.capabilities
    if tier == "bronze":
        return caps.shared.bronze
    if tier == "silver":
        return caps.shared.silver
    if tier == "gold":
        return caps.signature.get(force_id)
    return None


def resolve_quests(state: dict, moves: list[dict], config, seed: int) -> dict:
    """(state, moves, config, seed) -> phase-8 state delta.

    Returns a dict with:
      essence_changes:     {actor: rewards earned minus stakes charged}
      reputation_changes:  {adventurer_id: {force_id: clamped delta}}
      quest_progress:      {quest_id: new progress} for still-active quests
      quests_resolved:     {quest_id: "success" | "failure"}
      quest_claims:        {quest_id: new claimed_by list}
      quest_markers:       {quest_id: {marker: True}} guild markers set now
      capability_grants:   {adventurer_id: [newly conferred capabilities]}
      guild_completions:   {adventurer_id: {force_id: [newly completed tiers]}}
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
    quest_markers: dict[str, dict[str, bool]] = {}
    capability_grants: dict[str, list[str]] = {}
    guild_completions: dict[str, dict[str, list[str]]] = {}
    deaths: list[dict] = []
    graveyard_additions: list[dict] = []
    rejected: list[dict] = []

    def add_essence(actor: str, amount: int) -> None:
        essence_changes[actor] = essence_changes.get(actor, 0) + amount

    def current_essence(actor: str) -> int:
        pool = state["adventurers"] if actor.startswith("adventurer-") else state["forces"]
        return pool[actor]["essence"] + essence_changes.get(actor, 0)

    def apply_reputation(adventurer_id: str, force_id: str, delta: int) -> None:
        reputation = state["adventurers"][adventurer_id]["reputation"]
        pending = reputation_changes.setdefault(adventurer_id, {})
        current = reputation[force_id] + pending.get(force_id, 0)
        clamped = max(
            config.reputation.scale_min,
            min(config.reputation.scale_max, current + delta),
        )
        pending[force_id] = pending.get(force_id, 0) + clamped - current

    def grant_capability(adventurer_id: str, capability: str) -> None:
        held = state["adventurers"][adventurer_id].get("capabilities", [])
        if capability in held:
            return
        pending = capability_grants.setdefault(adventurer_id, [])
        if capability not in pending:
            pending.append(capability)

    def record_completion(adventurer_id: str, force_id: str, tier: str) -> None:
        completed = (
            state["adventurers"][adventurer_id]
            .get("guild", {})
            .get(force_id, {})
            .get("completed", [])
        )
        if tier in completed:
            return
        pending = guild_completions.setdefault(adventurer_id, {}).setdefault(force_id, [])
        if tier not in pending:
            pending.append(tier)

    def reject(actor: str, index: int, reason: str) -> None:
        rejected.append({"actor": actor, "index": index, "reason": reason})

    # markers set this tick, consulted alongside quest.params during verify
    new_markers: dict[str, set[str]] = {}
    entrench_bonus: dict[str, set[str]] = {}

    def marked(quest_id: str, quest: dict, marker: str) -> bool:
        return quest["params"].get(marker, False) or marker in new_markers.get(quest_id, set())

    # --- pass 0: guild markers (insure/entrench/wager) -----------------------
    _ACTION_MARKER = {"insure": "insured", "entrench": "entrenched", "wager": "wagered"}
    for batch in sorted(moves, key=lambda b: b["actor"]):
        actor = batch["actor"]
        for index, order in enumerate(batch["orders"]):
            action = order.get("action")
            if action not in _ACTION_MARKER:
                continue
            quest_id = order.get("quest_id")
            if not actor.startswith("adventurer-") or actor not in state["adventurers"]:
                reject(actor, index, f"{action}: no living adventurer entity")
                continue
            quest = active.get(quest_id)
            if quest is None:
                reject(actor, index, f"{action}: {quest_id} is not an active quest")
                continue
            if quest["params"].get("guild_tier") is None:
                reject(actor, index, f"{action}: {quest_id} is not a guild quest")
                continue
            if actor not in quest["claimed_by"]:
                reject(actor, index, f"{action}: not a claimant of {quest_id}")
                continue
            if action not in state["adventurers"][actor].get("capabilities", []):
                reject(actor, index, f"{action}: capability not unlocked")
                continue
            marker = _ACTION_MARKER[action]
            if marked(quest_id, quest, marker):
                reject(actor, index, f"{action}: {quest_id} already {marker}")
                continue
            if action == "entrench" and quest["type"] != "hold":
                reject(actor, index, f"entrench: {quest_id} is not a hold quest")
                continue
            cost = getattr(config.guild.capabilities.costs, action)
            if current_essence(actor) < cost:
                reject(actor, index,
                       f"{action}: cost {cost} exceeds {actor}'s "
                       f"{current_essence(actor)} essence")
                continue
            add_essence(actor, -cost)
            new_markers.setdefault(quest_id, set()).add(marker)
            quest_markers.setdefault(quest_id, {})[marker] = True
            if action == "entrench":
                entrench_bonus.setdefault(quest_id, set()).add(actor)

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
            elif quest["type"] in ("blockade", "hold"):
                # hold reuses the blockade streak verbatim, only the claimant
                # differs (an adventurer standing on X vs a force owning it).
                streaks = {}
                for claimant in claimants:
                    base = quest["progress"].get(claimant, 0)
                    if claimant in entrench_bonus.get(quest_id, set()):
                        base += 1  # +1 progress this tick (equiv. -1 tick)
                    streak = base + 1 if _occupies(state, claimant, quest["params"]["region"]) else 0
                    streaks[claimant] = streak
                fulfilled = any(s >= quest["params"]["n_ticks"] for s in streaks.values())
                if not fulfilled:
                    quest_progress[quest_id] = streaks
            elif quest["type"] == "travel":
                # reached X at any tick <= deadline; verification runs every
                # tick, so "at some tick" is satisfied the tick position == X.
                fulfilled = any(
                    _occupies(state, claimant, quest["params"]["region"])
                    for claimant in claimants
                )
            elif quest["type"] == "attrition":
                fulfilled = _force_units(state, quest["params"]["force"]) <= (
                    quest["params"]["units_at_spawn"] - quest["params"]["delta"]
                )
            elif quest["type"] == "dethrone":
                fulfilled = state["supremacy"]["streaks"].get(quest["params"]["force"], 0) == 0

        if fulfilled:
            quests_resolved[quest_id] = "success"
            quest_progress.pop(quest_id, None)
            guild_tier = quest["params"].get("guild_tier")
            if guild_tier is not None:
                # Guild success: the adventurer allies with the board force
                # (positive reputation, no rivals, no damage). Bronze pays via
                # a seeded coin-flip; higher tiers pay flat; a wagered board
                # doubles the essence. Completing the tier records it and
                # confers its capability (below).
                force_id = quest["params"]["force"]
                wagered = marked(quest_id, quest, "wagered")
                for claimant in claimants:
                    if guild_tier == "bronze":
                        coin = int(hashlib.sha256(
                            f"{seed}:{tick}:{claimant}:{quest_id}".encode("utf-8")
                        ).hexdigest(), 16)
                        hit = coin % 2 == 0
                        if hit:
                            essence = config.guild.rewards.essence.bronze_hit
                        else:
                            # a wagered miss forfeits the consolation (nada)
                            essence = 0 if wagered else config.guild.rewards.essence.bronze_miss
                        if wagered and hit:
                            essence *= 2
                        rep_gain = config.guild.rewards.reputation.bronze if hit else 0
                    else:
                        essence = getattr(config.guild.rewards.essence, guild_tier)
                        if wagered:
                            essence *= 2  # double the essence only; reputation intact
                        rep_gain = getattr(config.guild.rewards.reputation, guild_tier)
                    add_essence(claimant, essence)
                    if claimant.startswith("adventurer-"):
                        if rep_gain:
                            apply_reputation(claimant, force_id, rep_gain)
                        # completing a tier records it and confers its
                        # capability (a Bronze miss still completes the tier);
                        # Platinum records but grants no capability in v1.
                        record_completion(claimant, force_id, guild_tier)
                        capability = _tier_capability(config, guild_tier, force_id)
                        if capability is not None:
                            grant_capability(claimant, capability)
            else:
                damaged = quest["params"].get("force")
                for claimant in claimants:
                    add_essence(claimant, quest["reward"])
                    if claimant.startswith("adventurer-") and damaged is not None:
                        for force_id in sorted(state["forces"]):
                            delta = (
                                config.reputation.deltas.quest_damages_force
                                if force_id == damaged
                                else config.reputation.deltas.quest_damages_force_rivals
                            )
                            apply_reputation(claimant, force_id, delta)
        elif tick > quest["deadline"]:
            quests_resolved[quest_id] = "failure"
            quest_progress.pop(quest_id, None)
            insured = marked(quest_id, quest, "insured")
            for claimant in claimants:
                if claimant.startswith("adventurer-"):
                    adventurer = state["adventurers"].get(claimant)
                    if adventurer is None:
                        continue
                    if insured:
                        # refund the stake before the zero-essence check so
                        # insurance can pull the adventurer back from death
                        add_essence(claimant, quest["stake"])
                    if current_essence(claimant) == 0:
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
        "quest_markers": {
            qid: dict(sorted(markers.items()))
            for qid, markers in sorted(quest_markers.items())
        },
        "capability_grants": {
            aid: sorted(caps) for aid, caps in sorted(capability_grants.items())
        },
        "guild_completions": {
            aid: {fid: sorted(tiers) for fid, tiers in sorted(by_force.items())}
            for aid, by_force in sorted(guild_completions.items())
        },
        "adventurer_deaths": deaths,
        "graveyard_additions": graveyard_additions,
        "rejected_orders": rejected,
    }
