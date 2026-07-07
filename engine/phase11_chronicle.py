"""Phase 11 of the resolution order: the chronicle.

Emits ``/chronicle/tick-<N>.md`` content following the frozen template
in docs/intent.md (Apéndice — Plantilla de chronicle) byte for byte:
seven fixed sections as Markdown pipe tables, always present, with
key-value footer lines that always render (``-`` when empty). One
artifact, three consumers: the eval harness (regex), humans (GitHub
table rendering), and the lore LLM (input).

Lore itself is deliberately absent: per the golden rule, generated
text lives only in /lore/, produced outside the engine and never read
by adjudication. This phase is the last link of the deterministic
chain, not the first link of the generative one.

Inputs ride the working state: the final post-tick values plus the
transient ``tick_events`` bundle the resolver assembles from the
earlier phases' deltas (batches, substitutions, aggregated rejections,
staged collisions, combat rounds, yields, quest lifecycle, adventurer
events, and the phase-10 supremacy delta).

Pure function: no input mutation, no I/O, no wall clock, no randomness.
"""


def _params(order: dict) -> str:
    pairs = [f"{k}={order[k]}" for k in sorted(order) if k != "action" and order[k] is not None]
    return " ".join(pairs) if pairs else "-"


def _orders_section(events: dict) -> list[str]:
    lines = [
        "## Órdenes",
        "",
        "| actor | origen | # | acción | parámetros | estado |",
        "|---|---|---|---|---|---|",
    ]
    rejected = {
        (r["actor"], r["index"]): r["reason"] for r in events["rejected_orders"]
    }
    for batch in sorted(events["batches"], key=lambda b: b["actor"]):
        if not batch["orders"]:
            lines.append(f"| {batch['actor']} | {batch['origin']} | - | no-op | - | - |")
            continue
        for index, order in enumerate(batch["orders"]):
            reason = rejected.get((batch["actor"], index))
            estado = "válida" if reason is None else f"rechazada: {reason}"
            lines.append(
                f"| {batch['actor']} | {batch['origin']} | {index} "
                f"| {order['action']} | {_params(order)} | {estado} |"
            )
    subs = "; ".join(f"{s['actor']} ({s['reason']})" for s in events["substitutions"])
    lines += ["", f"Sustituciones: {subs if subs else '-'}"]
    return lines


def _combats_section(events: dict) -> list[str]:
    lines = [
        "## Combates",
        "",
        "| región | atacante | unidades_atq | defensor | unidades_def | poder_def | ganador | sup_atq | sup_def |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for combat in sorted(events["combats"], key=lambda c: c["region"]):
        for r in combat["rounds"]:
            defender = r["defender"] if r["defender"] is not None else "-"
            winner = r["winner"] if r["winner"] is not None else "-"
            lines.append(
                f"| {combat['region']} | {r['attacker']} | {r['attacker_units']} "
                f"| {defender} | {r['defender_units']} | {r['defender_power']} "
                f"| {winner} | {r['attacker_survivors']} | {r['defender_survivors']} |"
            )
    return lines


def _collisions_section(events: dict) -> list[str]:
    lines = ["## Colisiones", "", "| región | orden_por_hash |", "|---|---|"]
    for staged in sorted(events["pending_combats"], key=lambda c: c["region"]):
        order = ", ".join(p["actor"] for p in staged["parties"])
        lines.append(f"| {staged['region']} | {order} |")
    return lines


def _economy_section(state: dict, events: dict) -> list[str]:
    lines = ["## Economía", "", "| fuerza | rendimiento | esencia |", "|---|---|---|"]
    for force_id in sorted(state["forces"]):
        lines.append(
            f"| {force_id} | {events['yields'].get(force_id, 0)} "
            f"| {state['forces'][force_id]['essence']} |"
        )
    return lines


def _quests_section(state: dict, events: dict) -> list[str]:
    lines = ["## Quests", "", "| id | evento | tipo | tier | detalle |",
             "|---|---|---|---|---|"]
    for quest_id in sorted(events["quests_spawned"]):
        quest = events["quests_spawned"][quest_id]
        detail = f"deadline={quest['deadline']}"
        extra = _params(quest["params"])
        if extra != "-":
            detail += f" {extra}"
        lines.append(
            f"| {quest_id} | spawn | {quest['type']} | {quest['tier']} | {detail} |"
        )
    for quest_id in sorted(events["quests_resolved"]):
        status = events["quests_resolved"][quest_id]
        quest = state["quests"]["resolved"][quest_id]
        evento = "resuelta" if status == "success" else "expirada"
        lines.append(f"| {quest_id} | {evento} | {quest['type']} | {quest['tier']} | - |")
    return lines


def _supremacy_section(state: dict, events: dict, config) -> list[str]:
    lines = ["## Supremacía", "", "| fuerza | regiones | pct | streak | k_restante |",
             "|---|---|---|---|---|"]
    total = len(state["regions"])
    counts = {force_id: 0 for force_id in state["forces"]}
    for region in state["regions"].values():
        if region["owner"] in counts:
            counts[region["owner"]] += 1
    streaks = events["supremacy"]["supremacy"]["streaks"]
    for force_id in sorted(counts):
        streak = streaks.get(force_id, 0)
        remaining = max(0, config.coronation.k_ticks - streak)
        pct = f"{100 * counts[force_id] / total:.1f}%"
        lines.append(f"| {force_id} | {counts[force_id]} | {pct} | {streak} | {remaining} |")
    coronation = events["supremacy"]["coronation"] or "-"
    era_ends = events["supremacy"]["era_ends"] or "-"
    lines += ["", f"Coronación: {coronation}", f"Fin de era: {era_ends}"]
    return lines


def _adventurer_section(state: dict, events: dict) -> list[str]:
    lines = ["## Aventurero", "", "| id | posición | esencia | reputaciones | eventos |",
             "|---|---|---|---|---|"]
    for adventurer_id in sorted(state["adventurers"]):
        adventurer = state["adventurers"][adventurer_id]
        reputation = " ".join(
            f"{force_id}:{value}"
            for force_id, value in sorted(adventurer["reputation"].items())
        )
        tokens = []
        if adventurer_id in events["adventurer_spawned"]:
            tokens.append("spawn")
        if adventurer_id in events["adventurer_moves"]:
            tokens.append(f"move:{events['adventurer_moves'][adventurer_id]}")
        if adventurer_id in events["loot_claims"]:
            tokens.append(f"botín:+{events['loot_claims'][adventurer_id]}")
        eventos = "; ".join(tokens) if tokens else "-"
        lines.append(
            f"| {adventurer_id} | {adventurer['position']} | {adventurer['essence']} "
            f"| {reputation} | {eventos} |"
        )
    for death in events["adventurer_deaths"]:
        killer = death["killer"] if death["killer"] is not None else "-"
        lines.append(f"| {death['id']} | † {death['region']} | - | - | muerte:{killer} |")
    return lines


def resolve_chronicle(state: dict, moves: list, config, seed: int) -> dict:
    """(state, moves, config, seed) -> {"chronicle": markdown string}.

    ``state`` is the fully applied post-tick working state carrying the
    transient ``tick_events`` bundle; ``moves`` and ``seed`` are part of
    the uniform phase signature and unused. The resolver writes the
    string to /chronicle/tick-<N>.md verbatim.
    """
    tick = state["tick"] + 1
    events = state["tick_events"]

    lines = [f"# Crónica — era {config.era.number} — tick {tick}", ""]
    for section in (
        _orders_section(events),
        _combats_section(events),
        _collisions_section(events),
        _economy_section(state, events),
        _quests_section(state, events),
        _supremacy_section(state, events, config),
        _adventurer_section(state, events),
    ):
        lines.extend(section)
        lines.append("")

    return {"chronicle": "\n".join(lines[:-1]) + "\n"}
