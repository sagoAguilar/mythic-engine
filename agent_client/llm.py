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


def generate_orders(
    system_prompt: str,
    user_prompt: str,
    move_schema: dict,
    config: LLMConfig,
    client=None,
) -> list:
    """Call Claude with tool-use forced to the `orders` shape; return that list.

    *client* is an injected Anthropic-compatible client for testing; when
    None, a real ``anthropic.Anthropic()`` is constructed (requires
    ``ANTHROPIC_API_KEY`` in the environment).
    """
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
