"""Renders context + persona into the system/user prompt halves.

Numbers (costs, caps, thresholds) are read live from the loaded
``EraConfig`` and world state, never paraphrased here - so the prompt
cannot drift from the frozen parameters docs/intent.md declares as the
single source of truth. The order *shape* is likewise never restated in
prose: it is enforced by the tool schema passed alongside these prompts
(agent_client/llm.py), not by asking nicely.
"""

import yaml


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
        "## Current world state",
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
