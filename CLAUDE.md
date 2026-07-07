# CLAUDE.md — mythic-engine

## Source of truth

`docs/intent.md` is the complete, closed design spec. Every game rule, formula, parameter, and boundary lives there. This file governs *how* you build; that file governs *what* exists.

**Stop rule:** if you encounter any ambiguity not covered by `docs/intent.md`, STOP and ask. Never invent game rules, parameter values, tiebreakers, or resolution semantics. A wrong guess here silently corrupts an eval; a question costs one turn.

## The golden rule

No LLM-generated token ever enters the adjudication chain. The arbiter is deterministic code. `/lore/` is write-only output — nothing in `engine/` may read it. If a change would make resolution depend on generated text, it is wrong by definition.

## Architecture constraints

- `engine/` is pure Python with zero GitHub imports and zero network calls. Entry point: `engine.resolve(state_dir, moves_dir, seed)` → writes next-tick state. The GitHub Actions workflow is a thin shell around this call; all logic must be testable offline.
- Agents propose (one new file in `/moves/tick-N/`); only the arbiter writes `/world/`. The engine must also validate its own output against `schema/world.schema.json` — the arbiter is caged too.
- All randomness derives from `hash(seed, tick, ...)`. No `random` module without an explicit seed chain. No wall-clock reads inside resolution.
- All tunable values come from `world/era.yml`. Never hardcode a number that the spec declares as a parameter.

## Definition of done

The master test: resolving the same fixture twice produces byte-identical output directories. Until this passes, nothing else matters. Every phase of the 11-phase resolution order ships with its own fixture under `tests/fixtures/` (e.g. `tick_combate_simple/`, `tick_colision_espejo/`, `tick_npc_sustitucion/`, `tick_rubberband_spawn/`).

## Working method

- TDD, one resolution phase per PR, in the order defined in `docs/intent.md` (11 phases). Fixture first, then implementation.
- Commit sequence: skeleton → `era.yml` → map generator + rotational-isomorphism test → schemas → engine phases → `resolve.yml` workflow. Do not skip ahead.
- Small diffs. One phase, one PR. Do not build the agent client until the tracer bullet passes: 3 hardcoded move PRs → tick resolved on main with chronicle → local replay byte-identical.
- Chronicle output must match the template in `docs/intent.md` exactly — it is a parsing contract for the eval harness, not prose.

## Non-goals (do not build)

Fog of war, real subagent delegation, force-issued quests, inheritance on death, mechanical faction asymmetry, Telegram bot, multi-resource economy, spectator frontend. All explicitly deferred in `docs/intent.md` boundaries. If a task seems to need one of these, invoke the stop rule.
