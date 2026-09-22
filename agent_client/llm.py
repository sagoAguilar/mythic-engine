"""Anthropic-backed order generation.

This is the one module in this package allowed to touch the network -
``engine/`` must stay pure Python with zero network calls (CLAUDE.md); the
agent client is deliberately outside ``engine/`` so that constraint holds.

The model never controls ``actor``/``tick``/``origin``: the tool schema
exposed to it is trimmed to just the `orders` shape from
schema/move.schema.json, and the caller (agent_client/client.py) fills in
the rest. That keeps the golden rule intact even inside a package that
calls an LLM - the model proposes orders, it never writes state or the
move envelope itself.
"""

from dataclasses import dataclass


class LLMError(Exception):
    """The LLM backend failed to return a usable tool call."""


@dataclass(frozen=True)
class LLMConfig:
    model: str = "claude-sonnet-5"
    max_tokens: int = 1024


def _orders_tool_schema(move_schema: dict) -> dict:
    return {
        "type": "object",
        "properties": {"orders": move_schema["properties"]["orders"]},
        "required": ["orders"],
        "additionalProperties": False,
        "$defs": move_schema["$defs"],
    }


def _generate_orders_via_cli(
    system_prompt: str, user_prompt: str, move_schema: dict
) -> list:
    """Fallback: call the `claude -p` CLI subprocess when no API key is set.

    Requires the claude CLI on PATH and either CLAUDE_CODE_OAUTH_TOKEN or
    existing CLI auth in the environment.  The CLI lacks forced tool-use, so
    we ask for raw JSON in the prompt and parse it out of the response.
    """
    import json
    import re
    import subprocess

    combined = (
        f"{system_prompt}\n\n"
        f"{user_prompt}\n\n"
        "Respond with ONLY a JSON object — no prose, no markdown fences:\n"
        '{"orders": [...]}\n'
    )
    result = subprocess.run(
        ["claude", "-p", combined, "--output-format", "json"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise LLMError(
            f"claude CLI exited {result.returncode}: {result.stderr[:300]}"
        )
    wrapper = json.loads(result.stdout)
    text = wrapper.get("result") or wrapper.get("content") or ""
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise LLMError(f"no JSON object in CLI response: {text[:200]}")
    data = json.loads(match.group())
    orders = data.get("orders")
    if not isinstance(orders, list):
        raise LLMError("CLI response missing 'orders' list")
    return orders


def generate_orders(
    system_prompt: str,
    user_prompt: str,
    move_schema: dict,
    config: LLMConfig,
    client=None,
) -> list:
    """Call Claude; return the proposed orders list.

    When *client* is None the backend is chosen automatically:
    - ``ANTHROPIC_API_KEY`` present → Anthropic Python SDK (tool-use)
    - no API key → ``claude -p`` CLI subprocess (requires CLI on PATH +
      ``CLAUDE_CODE_OAUTH_TOKEN`` or existing CLI auth)

    Pass an explicit *client* to inject a test double.
    """
    import os

    if client is None and not os.environ.get("ANTHROPIC_API_KEY"):
        return _generate_orders_via_cli(system_prompt, user_prompt, move_schema)

    if client is None:
        import anthropic

        client = anthropic.Anthropic()

    tool = {
        "name": "propose_orders",
        "description": "Propose this tick's order batch for your force.",
        "input_schema": _orders_tool_schema(move_schema),
    }
    response = client.messages.create(
        model=config.model,
        max_tokens=config.max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        tools=[tool],
        tool_choice={"type": "tool", "name": "propose_orders"},
    )
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "propose_orders":
            orders = block.input.get("orders")
            if not isinstance(orders, list):
                raise LLMError("propose_orders call is missing an `orders` list")
            return orders
    raise LLMError("no propose_orders tool call in the model's response")
