"""Renders context + persona into the system/user prompt halves.

Numbers (costs, caps, thresholds) are read live from the loaded
``EraConfig`` and world state, never paraphrased here - so the prompt
cannot drift from the frozen parameters docs/intent.md declares as the
single source of truth. The order *shape* is likewise never restated in
prose: it is enforced by the tool schema passed alongside these prompts
(agent_client/llm.py), not by asking nicely.
"""

import yaml


def _render_disposal(disposal: dict) -> str:
    lines = [f"Essence available: {disposal['essence']}", "", "Regions you own:"]
    for region_id, info in sorted(disposal["regions"].items()):
        neighbors = ", ".join(
            f"{n['id']} ({n['owner'] or 'neutral'})" for n in info["adjacent"]
        )
        lines.append(
            f"  {region_id}: units={info['units']} fortification={info['fortification']} "
            f"yield={info['yield']} adjacent=[{neighbors}]"
        )
    lines.append("")
    if disposal["eligible_quests"]:
        lines.append("Quests you're eligible to accept:")
        for quest_id, quest in sorted(disposal["eligible_quests"].items()):
            lines.append(
                f"  {quest_id}: type={quest['type']} tier={quest['tier']} "
                f"reward={quest['reward']} stake={quest['stake']} "
                f"deadline={quest['deadline']}"
            )
    else:
        lines.append("Quests you're eligible to accept: none active")
    return "\n".join(lines)


def build_system_prompt(persona: str) -> str:
    return (
        f"{persona.strip()}\n\n"
        "You command one of three forces in a deterministic strategy game "
        "played over pull requests. Call propose_orders exactly once with "
        "the batch of orders you want this tick. You only control the "
        "`orders` list - the engine assigns actor/tick/origin itself, and "
        "validates every order you propose against a fixed schema and your "
        "order cap. A batch that fails validation or exceeds the cap is "
        "rejected outright, never partially applied, and you will be asked "
        "to correct it."
    )


def build_user_prompt(ctx: dict, config, prior_errors: list[str]) -> str:
    state = ctx["state"]
    parts = [
        f"Tick to decide: {ctx['tick']}",
        f"Your force: {ctx['force_id']}",
        f"Order cap this tick: {config.orders.cap_force}",
        "",
        "## Your disposal this tick",
        _render_disposal(ctx["disposal"]),
        "",
        "## Current world state (full, for context beyond your own regions)",
        yaml.safe_dump(state, sort_keys=True),
        "",
        "## Move history (all actors, all resolved ticks)",
        yaml.safe_dump(ctx["history"], sort_keys=False) if ctx["history"] else "(none yet)",
    ]
    if prior_errors:
        parts += [
            "",
            "## Your previous proposal was rejected",
            "\n".join(prior_errors),
            "Propose a corrected batch.",
        ]
    return "\n".join(parts)
