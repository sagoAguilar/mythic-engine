"""Phase 9 of the resolution order: quest spawning by triggers.

Three v1 sources (docs/intent.md; forces-as-emitters is v2):

**Vengeance** (era.yml trigger table): each adventurer killed this tick
by a force spawns a quest of the configured type against the killer —
processed first, in death order, so it wins contested slots. Deaths
arrive on the working state as the transient
``adventurer_deaths_this_tick`` (recorded by phases 5 and 8);
killer-less deaths trigger nothing.

**Rubber band**: fires only against a strict unique leader (most owned
regions; a tie spawns nothing, mirroring the strict-minimum spawn
rule). Leader fraction > supremacy_minor opens the minor slots,
> supremacy_major the major slot. Slots top up to the frozen
composition cap (max 1 major + 2 minors active) each tick the trigger
holds: minors in fixed order raid then blockade, the major slot
spawning dethrone once the leader has a supremacy streak and attrition
otherwise. No dedupe by type — the cap is the only intensity limiter.

**Guild boards** (docs/intent.md point 9): a fourth deterministic
source, spawned last so it never shares the rubber-band cap. Each
capital's board offers one active quest per tier the sole living
adventurer can currently reach — Bronze (rep >= 0) through Platinum
(rep >= threshold *and* that force reduced to <= platinum_condition
regions). A ``(force, tier)`` slot holds at most one active guild quest;
an occupied slot is left alone, an empty one refilled. Type and target
come from a single seeded hash ``sha256(seed:tick:guild:force:tier)``:
even -> ``travel`` (reach region X, X = seeded pick over every region
except the adventurer's position), odd -> ``hold`` (occupy X for N
ticks, X = seeded neutral like blockade). Guild spawn is a no-op unless
exactly one adventurer is alive — multi-adventurer interaction is v1-
deferred, so a two-adventurer state (e.g. mid-tick after a spawn)
produces no boards.

Frozen parameter formulas: raid X = the target force's least-garrisoned
region (ties by lowest lexical id); blockade X = seeded pick
sha256(seed:tick:blockade) % n over the sorted neutrals adjacent to the
leader (skipped when none exist); T = tick + window_ticks; N and D and
all rewards/stakes from era.yml. Guild travel deadline = tick +
guild.objectives.travel_deadline[tier]; guild hold deadline = tick +
window_ticks; guild reward field = 0 for Bronze (coin-flip paid in
phase 8) and the flat per-tier essence otherwise. Quest ids are
``<type>-<tick>-<seq>`` with seq counting spawns within the tick.

Pure function: no input mutation, no I/O, no wall clock; the only
randomness is the seeded blockade and guild-board picks.
"""

import hashlib

GUILD_TIERS = ("bronze", "silver", "gold", "platinum")


def _least_garrisoned(state: dict, force_id: str) -> str | None:
    owned = [
        (region["units"], region_id)
        for region_id, region in state["regions"].items()
        if region["owner"] == force_id
    ]
    return min(owned)[1] if owned else None


def _sole_living_adventurer(state: dict) -> dict | None:
    """The single living adventurer, or None when zero or several are alive.

    Guild boards are a single-adventurer mechanic in v1 (docs/intent.md);
    with no adventurer there is no one to quest, and with several the
    interaction is deferred, so both cases spawn nothing.
    """
    adventurers = state.get("adventurers", {})
    if len(adventurers) != 1:
        return None
    return next(iter(adventurers.values()))


def _force_region_count(state: dict, force_id: str) -> int:
    return sum(1 for r in state["regions"].values() if r["owner"] == force_id)


def _strict_leader(state: dict) -> tuple[str | None, int]:
    counts = {force_id: 0 for force_id in state["forces"]}
    for region in state["regions"].values():
        if region["owner"] in counts:
            counts[region["owner"]] += 1
    ranked = sorted(counts.values(), reverse=True)
    if not counts or (len(ranked) >= 2 and ranked[0] == ranked[1]):
        return None, 0
    leader = max(counts, key=counts.get)
    return leader, counts[leader]


def resolve_quest_spawn(state: dict, moves: list, config, seed: int) -> dict:
    """(state, moves, config, seed) -> phase-9 state delta.

    Returns {"quests_spawned": {quest_id: quest object}}. ``moves`` is
    part of the uniform phase signature and unused — spawning is driven
    by state and era.yml alone.
    """
    tick = state["tick"] + 1
    active = state["quests"]["active"]

    # guild boards carry the rubber band's `tier` only for the stake bucket;
    # they never share its composition cap (docstring: "never shares the
    # rubber-band cap"), so an active guild board is not counted here.
    _GUILD_TYPES = ("travel", "hold")
    minors = sum(
        1 for q in active.values()
        if q["tier"] == "minor" and q["type"] not in _GUILD_TYPES
    )
    majors = sum(
        1 for q in active.values()
        if q["tier"] == "major" and q["type"] not in _GUILD_TYPES
    )
    spawned: dict[str, dict] = {}
    seq = 0

    def spawn(quest_type: str, tier: str, params: dict) -> None:
        nonlocal seq, minors, majors
        seq += 1
        quest_id = f"{quest_type}-{tick}-{seq}"
        spawned[quest_id] = {
            "id": quest_id,
            "type": quest_type,
            "tier": tier,
            "eligibility": "any" if tier == "minor" else "forces",
            "reward": getattr(config.quests.rewards, quest_type),
            "stake": config.quests.stakes.minor if tier == "minor" else config.quests.stakes.major,
            "deadline": tick + config.quests.window_ticks,
            "max_claimants": "open" if tier == "minor" else 1,
            "claimed_by": [],
            "progress": {},
            "params": params,
        }
        if tier == "minor":
            minors += 1
        else:
            majors += 1

    # --- vengeance first: it wins contested slots ----------------------------
    for death in state.get("adventurer_deaths_this_tick", []):
        killer = death["killer"]
        if killer is None or minors >= config.quests.max_active_minor:
            continue
        target = _least_garrisoned(state, killer)
        if target is None:
            continue
        spawn(config.quests.triggers.adventurer_death_vengeance, "minor",
              {"region": target, "force": killer})

    # --- rubber band against a strict unique leader ---------------------------
    leader, region_count = _strict_leader(state)
    if leader is not None:
        fraction = region_count / len(state["regions"])

        if fraction > config.quests.triggers.supremacy_minor:
            if minors < config.quests.max_active_minor:
                target = _least_garrisoned(state, leader)
                if target is not None:
                    spawn("raid", "minor", {"region": target, "force": leader})
            if minors < config.quests.max_active_minor:
                candidates = sorted(
                    region_id
                    for region_id, region in state["regions"].items()
                    if region["owner"] is None and any(
                        state["regions"][adj]["owner"] == leader
                        for adj in region["adjacent"]
                    )
                )
                if candidates:
                    pick = int(
                        hashlib.sha256(f"{seed}:{tick}:blockade".encode("utf-8")).hexdigest(),
                        16,
                    ) % len(candidates)
                    spawn("blockade", "minor", {
                        "region": candidates[pick],
                        "n_ticks": config.quests.blockade_n_ticks,
                        "force": leader,
                    })

        if fraction > config.quests.triggers.supremacy_major and majors < config.quests.max_active_major:
            if state["supremacy"]["streaks"].get(leader, 0) > 0:
                spawn("dethrone", "major", {"force": leader})
            else:
                units = sum(
                    r["units"] for r in state["regions"].values() if r["owner"] == leader
                )
                spawn("attrition", "major", {
                    "force": leader,
                    "units_at_spawn": units,
                    "delta": config.quests.attrition_delta,
                })

    # --- guild boards: one quest per accessible, unoccupied (force, tier) -----
    adventurer = _sole_living_adventurer(state)
    if adventurer is not None:
        guild = config.guild
        occupied = {
            (q["params"]["force"], q["params"]["guild_tier"])
            for q in active.values()
            if q.get("eligibility") == "adventurer" and "guild_tier" in q.get("params", {})
        }
        for force_id in sorted(state["forces"]):
            reputation = adventurer["reputation"].get(force_id, 0)
            for tier in GUILD_TIERS:
                if reputation < getattr(guild.thresholds, tier):
                    continue
                if tier == "platinum" and (
                    _force_region_count(state, force_id)
                    > guild.platinum_condition.force_regions_max
                ):
                    continue
                if (force_id, tier) in occupied:
                    continue

                digest = hashlib.sha256(
                    f"{seed}:{tick}:guild:{force_id}:{tier}".encode("utf-8")
                ).hexdigest()
                h = int(digest, 16)
                quest_type = "travel" if h % 2 == 0 else "hold"
                if quest_type == "travel":
                    candidates = sorted(
                        r for r in state["regions"] if r != adventurer["position"]
                    )
                else:
                    candidates = sorted(
                        r for r, region in state["regions"].items()
                        if region["owner"] is None
                    )
                if not candidates:  # nowhere legal to send them this tick
                    continue
                region = candidates[h % len(candidates)]

                bucket = getattr(guild.stakes, tier)  # minor | major
                params = {"region": region, "force": force_id, "guild_tier": tier}
                if quest_type == "travel":
                    deadline = tick + getattr(guild.objectives.travel_deadline, tier)
                else:
                    params["n_ticks"] = getattr(guild.objectives.hold_n_ticks, tier)
                    deadline = tick + config.quests.window_ticks

                seq += 1
                quest_id = f"{quest_type}-{tick}-{seq}"
                spawned[quest_id] = {
                    "id": quest_id,
                    "type": quest_type,
                    "tier": bucket,
                    "eligibility": "adventurer",
                    "reward": 0 if tier == "bronze" else getattr(guild.rewards.essence, tier),
                    "stake": getattr(config.quests.stakes, bucket),
                    "deadline": deadline,
                    "max_claimants": 1,
                    "claimed_by": [],
                    "progress": {},
                    "params": params,
                }

    return {"quests_spawned": dict(sorted(spawned.items()))}
