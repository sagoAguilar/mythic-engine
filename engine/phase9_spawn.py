"""Phase 9 of the resolution order: quest spawning by triggers.

Two v1 sources (docs/intent.md; forces-as-emitters is v2):

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

Frozen parameter formulas: raid X = the target force's least-garrisoned
region (ties by lowest lexical id); blockade X = seeded pick
sha256(seed:tick:blockade) % n over the sorted neutrals adjacent to the
leader (skipped when none exist); T = tick + window_ticks; N and D and
all rewards/stakes from era.yml. Quest ids are ``<type>-<tick>-<seq>``
with seq counting spawns within the tick.

Pure function: no input mutation, no I/O, no wall clock; the only
randomness is the seeded blockade pick.
"""

import hashlib


def _least_garrisoned(state: dict, force_id: str) -> str | None:
    owned = [
        (region["units"], region_id)
        for region_id, region in state["regions"].items()
        if region["owner"] == force_id
    ]
    return min(owned)[1] if owned else None


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

    minors = sum(1 for q in active.values() if q["tier"] == "minor")
    majors = sum(1 for q in active.values() if q["tier"] == "major")
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
    if leader is None:
        return {"quests_spawned": dict(sorted(spawned.items()))}
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

    return {"quests_spawned": dict(sorted(spawned.items()))}
