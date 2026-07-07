# mythic-engine

A multi-agent eval presented as a continuous mythic world, played on GitHub primitives: versioned state, identity, deterministic adjudication via Actions, full replay via history.

- **Design spec:** [`docs/intent.md`](docs/intent.md) — the complete, closed source of truth for every game rule, formula, parameter, and boundary.
- **Working rules:** [`CLAUDE.md`](CLAUDE.md).

## Layout

```
engine/              # deterministic arbiter — pure Python, no network, no GitHub imports
schema/              # JSON Schemas for world state and moves
scripts/             # tooling (map generator, etc.)
tests/fixtures/      # one fixture per resolution phase
world/               # canonical game state — written only by the arbiter
.github/workflows/   # thin shell around engine.resolve()
```
