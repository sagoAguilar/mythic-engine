"""Phase 10 of the resolution order: supremacy counter / coronation.

Writes the ``supremacy`` block that phases 8 (dethrone) and 9 (rubber
band) read on later ticks. Per force, independently: holding strictly
more than ``supremacy_threshold`` of the regions this tick extends the
streak by one; anything else resets it to zero. Two forces can be
supreme at once (6/6 of 12 at threshold 0.45) and both streaks grow.
The ``leader`` is the strict unique region-count maximum, null on a
tie — the same reading phase 9 uses.

A streak reaching ``k_ticks`` coronates that force; in the (6/6)
freak case where two forces coronate on the same tick, the crown goes
by the seeded collision formula sha256(seed:tick:coronation:force),
never by force-id order. The era also ends when the resolving tick
reaches ``tick_cap``; a same-tick coronation takes precedence as the
recorded reason.

This phase only *flags* coronation and era end. The cataclysm — reset
to baseline, reputation halving, graveyard persistence, the next
era.yml — is era-transition tooling outside tick resolution; the
workflow acts on the flag.

Pure function: no input mutation, no I/O, no wall clock; the only
randomness is the coronation-tie pick.
"""

import hashlib


def resolve_supremacy(state: dict, moves: list, config, seed: int) -> dict:
    """(state, moves, config, seed) -> phase-10 state delta.

    Returns a dict with:
      supremacy:  the new block {leader, streaks} replacing state's
      coronation: force_id whose sustained supremacy reached K, else None
      era_ends:   "coronation" | "tick_cap" | None
    """
    tick = state["tick"] + 1
    total = len(state["regions"])

    counts = {force_id: 0 for force_id in state["forces"]}
    for region in state["regions"].values():
        if region["owner"] in counts:
            counts[region["owner"]] += 1

    streaks: dict[str, int] = {}
    for force_id in sorted(counts):
        supreme = counts[force_id] / total > config.coronation.supremacy_threshold
        streaks[force_id] = (
            state["supremacy"]["streaks"].get(force_id, 0) + 1 if supreme else 0
        )

    ranked = sorted(counts.values(), reverse=True)
    if len(ranked) >= 2 and ranked[0] == ranked[1]:
        leader = None
    else:
        leader = max(counts, key=counts.get) if counts else None

    coronated = [f for f in sorted(streaks) if streaks[f] >= config.coronation.k_ticks]
    if len(coronated) > 1:
        coronated.sort(
            key=lambda f: hashlib.sha256(
                f"{seed}:{tick}:coronation:{f}".encode("utf-8")
            ).hexdigest()
        )
    coronation = coronated[0] if coronated else None

    if coronation is not None:
        era_ends = "coronation"
    elif tick >= config.era.tick_cap:
        era_ends = "tick_cap"
    else:
        era_ends = None

    return {
        "supremacy": {"leader": leader, "streaks": streaks},
        "coronation": coronation,
        "era_ends": era_ends,
    }
