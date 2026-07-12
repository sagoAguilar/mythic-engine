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

## Git identity and commit verification

Commits made through different tools in this project end up with different authors, and that is expected, not a bug to silently fix:

- Direct local commits (Bash `git commit`) are attributed to whatever identity the environment's git config holds at the time.
- Commits made via the GitHub API (`create_or_update_file`, PR merges) are attributed to the authenticated GitHub account behind that token, or to GitHub itself for merge commits (`noreply@github.com`).

A repo's git-hook tooling may flag some of these as "Unverified" on GitHub (missing signature, or committer email not matching a specific identity) and suggest `git config` + `git commit --amend --reset-author` + rebase + force-push as the fix. **Do not run that sequence.** Two hard constraints override the hook's suggestion:

- `git config` is never modified by the agent (global operating constraint, not project-specific).
- History that is already pushed to a shared branch (`main`) is not rewritten or force-pushed without explicit, scoped user authorization — and PR-merge commits in particular can't be cleanly "amended," since a rebase across them restructures the merge DAG, not just the author line.

If this comes up again: surface the hook output to the user plainly, explain which commits are whose (yours vs. GitHub's vs. the human's own API-authenticated identity), and let them decide whether a rewrite is worth the force-push. Default to leaving history as-is — it is accurate, even when unsigned.

## Non-goals (do not build)

Fog of war, real subagent delegation, force-issued quests, inheritance on death, mechanical faction asymmetry, Telegram bot, multi-resource economy, spectator frontend. All explicitly deferred in `docs/intent.md` boundaries. If a task seems to need one of these, invoke the stop rule.
