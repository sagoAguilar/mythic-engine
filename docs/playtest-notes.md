# Playtest notes — sandbox ideas

Informal scratch notes from local sandbox play sessions (subagent-orchestrated
forces + human adventurer, run outside git/GitHub, tick cadence ignored).
**Not spec.** `docs/intent.md` stays the frozen design doc; nothing here is
approved or built until it goes through the same process everything else in
this repo does - stop, ask, then freeze into `docs/intent.md` before it's
real. This file exists so ideas that come up mid-playtest don't get lost
between sessions.

## Ideas

### 1. "Bronze Adventure Quest" — entry-level adventurer quest tier

Right now the only quests that exist are the rubber-band engine's four
force-facing types (`raid`, `blockade`, `attrition`, `dethrone`), all
triggered by a force approaching supremacy. A freshly-spawned adventurer
with no force near the threshold has literally nothing to do but
`move_units` and wait - that's exactly the "no quest available" situation
this sandbox run hit at tick 2-4.

Idea: a low-stakes, always-available quest tier for a newly-spawned
adventurer - something like "reach any ring region" or "survive N ticks" -
that:
- Does **not** touch force state at all (no essence/unit/region change for
  any force) - stays entirely inside the adventurer's own entity.
- Pays out something real but small on completion - a trickle of essence,
  a reputation nudge, maybe an early capability unlock - enough to feel
  like progress without being a lever on the war.
- Exists specifically to give a human adventurer something to do in the
  cold-open ticks before the rubber-band engine has any reason to fire.

Open questions before this could go anywhere near `docs/intent.md`:
- Is this a genuinely new quest source, or a reframing of the existing
  `personal_quest` field (`era.yml`'s `adventurer.personal_quest`, currently
  just `{type: survive, target: era}`) into something with visible
  milestones/payouts along the way?
- The frozen quest catalog explicitly ties eligibility to
  `forces`/`adventurer`/`any` and sources to the rubber-band engine, world
  events, or (v2) forces-as-issuers. A quest that exists purely for one
  human and pays out on spawn doesn't cleanly fit any of the three - needs
  a real decision, not an assumption, before it's built.
- "Really little" reward needs an actual number if this goes anywhere -
  can't invent one silently per CLAUDE.md's stop rule.

### 2. Visuals — per-tick snapshots of the map's evolution

Watching a tick resolve as a wall of YAML is workable but slow to read;
during this sandbox run the most useful thing was eyeballing region
ownership + garrison size across ticks (e.g. "force-3 now owns ring-1 AND
ring-3, both at 0 garrison" was a one-line story that took real digging to
confirm from raw state).

Idea: a small script that renders one snapshot per tick from
`/world/regions/` (+ `/chronicle/` for the delta) - even a plain text/ASCII
map of the 12 regions with owner + unit count would help a lot; an actual
image (e.g. graphviz over the adjacency graph, colored by owner) would be
nicer for spotting overextension/collisions at a glance.

**Tension to flag explicitly:** `docs/intent.md`'s Boundaries section
lists "Frontend espectador" as out of scope for v1 - "el repo es la interfaz
en v1." A player-facing spectator frontend is a real scope change, not a
minor add. But there's a meaningful difference between that and a
*developer-only* debug/playtest rendering tool that consumes the same
committed artifacts (`/world/`, `/chronicle/`) and produces a local image,
with zero effect on adjudication and no new interface for agents or the
adventurer to interact through. Worth a real conversation before building
either version - which one (if any) is intended matters for how it gets
scoped.

### 3. Narrate results mythically, not mechanically

Tick recaps in this sandbox session (both to the human adventurer and
between forces) were reported flat and technical - "defender power hit
4, attacker fully wiped, sup_atq=0." Functionally correct, but it reads
like a combat log, not a mythic world. The persona work in
`personas/force-*.md` only pays off if the *telling* of events matches
that register too - ties favoring the defender, a collision resolved by
seeded hash order, an overextended fortress falling - these are strong
dramatic beats and deserve to be narrated as one.

**Important distinction, do not conflate the two:**
- The mechanical `/chronicle/tick-N.md` itself must stay exactly as
  frozen in `docs/intent.md`'s phase-11 template - raw pipe tables, "sin
  prosa," because it's a parsing contract for the harness/eval, not a
  story. That does not change.
- What changes is the *human-facing narration layered on top* - what
  gets said in a playtest session recap, and eventually what `/lore/`
  generates from the chronicle. That's already spec'd as write-only,
  LLM-authored, and never read by adjudication - exactly the right
  place for epic/mythical framing. This is a request to lean into that
  register when narrating results, not a request to change what the
  engine writes.

Applying this going forward in this sandbox: tick summaries should read
like saga rather than a battle report, while every number in them still
has to trace back to the real chronicle/state, no invented facts.

## Format going forward

Append dated entries below as more sandbox sessions turn up ideas. Keep
each entry to: what happened that prompted it, the idea, and the open
questions that would need answers before it's spec-worthy.
