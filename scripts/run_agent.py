#!/usr/bin/env python3
"""CLI entry point for one force's local agent client.

Run once per force per tick, from a checkout that already has the
resolved state for the previous tick:

    python scripts/run_agent.py --force force-1

Writes moves/tick-<N>/<force>.yml using the persona already referenced by
world/forces/<force>.yml. Does not touch git or GitHub - PR submission is
a separate, manual step (docs/intent.md inventory item 6: "cliente de
agente, maquina local en v1").
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from agent_client.client import ClientError, generate_move, write_move  # noqa: E402
from agent_client.llm import LLMConfig  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", required=True, help="e.g. force-1")
    parser.add_argument(
        "--persona",
        type=Path,
        default=None,
        help="override the persona file (default: the force's own world/forces entry)",
    )
    parser.add_argument("--state-dir", type=Path, default=REPO_ROOT)
    parser.add_argument("--model", default=LLMConfig.model)
    parser.add_argument("--max-tokens", type=int, default=LLMConfig.max_tokens)
    parser.add_argument("--max-attempts", type=int, default=3)
    args = parser.parse_args()

    llm_config = LLMConfig(model=args.model, max_tokens=args.max_tokens)
    try:
        batch = generate_move(
            args.state_dir,
            args.force,
            persona_path=args.persona,
            llm_config=llm_config,
            max_attempts=args.max_attempts,
        )
    except ClientError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)

    path = write_move(args.state_dir, batch)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
