# mythic-engine

An adversarial multi-agent eval disguised as a mythic world, built entirely on GitHub primitives.

Three LLM-driven forces compete for dominance over a 12-region world. The repo is the game state. A commit is a tick. Moves are pull requests. GitHub Actions is the arbiter. The full history of every era — every order, every battle, every betrayal — is the eval dataset, reproducible by anyone with `git clone`.

## How it works

- **State** lives in `/world/` as YAML. Only the arbiter writes it.
- **Moves** are PRs adding one file to `/moves/tick-N/`. Agents (and one optional human adventurer) propose; the resolution workflow consumes, adjudicates, and commits the next tick.
- **Adjudication is deterministic.** Same state + same moves + same seed = same resolution, byte for byte. No LLM output ever enters the adjudication chain — generated text is confined to `/lore/`, which nothing in the engine reads.
- **The world fights the winner.** A rubber-band quest engine spawns missions against whoever approaches supremacy. Sustained dominance triggers coronation, cataclysm, and a new era.
- **Eras are runs.** One era = one eval unit. The harness reads `git log` and `/chronicle/` — no additional instrumentation.

## The adventurer

A human may join as an adventurer: same interface (PRs), same rules, same validator as the agents. Enter and leave freely — an absent adventurer runs on a deterministic NPC policy. The adventurer cannot win the war; they have their own quest, their own reputation with each force, and a graveyard that remembers them across eras.

## Status

Sandbox. This repository is an experiment in multi-agent evaluation, not a contribution-graph artifact. Design spec: [`docs/intent.md`](docs/intent.md).

## License

MIT
