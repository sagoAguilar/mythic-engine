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

## Session — 2026-07-20

Prompted by the first full sandbox playthrough (16 ticks, three
subagent forces + human adventurer): essence piled up with no ceiling
(one force ended at 22 units, 8 essence bricked with nothing left to
spend it on), the adventurer had nothing to do but move for the entire
run, and tick narration stayed flat even after note #3 above asked for
mythic framing of *results* - unit *counts* themselves still read as
bare integers.

### 4. Essence has no sink that scales with hoarding

Confirmed against the code, not assumption: `schema/world.schema.json`
caps nothing about a region's `units` field beyond `minimum: 0` - no
maximum, anywhere, for garrison size or total army. Fortification caps
at level 3 (`fortify_cap`), but `recruit` has no ceiling except whatever
essence can buy. In the sandbox run this meant essence functioned as a
one-way ratchet: yield in, garrison out, no cost that grows with what a
force already holds.

Idea: an **upkeep cost** - units cost essence per tick to maintain, so a
force with a large standing army now has a running expense, not just a
sunk one. Preferred over the alternatives considered:
- Essence stockpile decay: punishes saving for a specific push, feels
  arbitrary.
- Scaling `recruit_cost` with garrison size: treats the symptom (buying
  more) rather than the cause (holding more).

Open questions before this is spec-worthy:
- An upkeep cost changes the strategic value of every existing unit
  retroactively - it's a real rule change to F1's economic context, not
  a tuning knob, and needs its own fixture like any frozen mechanic
  (CLAUDE.md: one phase, one PR).
- The actual cost-per-unit number is not something to invent silently -
  needs a deliberate `era.yml` value, calibrated the same way F3's
  other constants were.

### 5. Trade (adventurer <-> force): payoff is defined, the flow isn't

`docs/intent.md` names trade as adventurer-only (forces never trade with
each other - "Reputación fuerza↔fuerza: rechazada en v1") and gives the
payoff precisely: +2 reputation/tick, capped at `trade_cap_per_tick: 3`.
What it does **not** say: what is actually exchanged. Essence for
reputation with no cost to the adventurer? Essence changing hands in
both directions? Something else entirely? `engine/phase8_quests.py` has
no trade logic at all right now (confirmed by reading it, not assumed) -
the parameter in `era.yml` is currently inert.

This is a real spec gap, not a design idea - flagging it rather than
proposing an answer, per the stop rule. Needs a decision on the actual
resource flow before any code can implement it.

### 6. Adventurer progression should be felt during play, not just at coronation

Sharpens idea #1 above. The frozen design already has reputation
thresholds (`era.yml`: trade≥10, refuge≥25, errands_v2≥40 unlock
things) and the "Legado" mechanic grants a diegetic title at
coronation if reputation clears a bar - but that's an epilogue, visible
only once an era ends. The ask: give the adventurer a sense of rank or
standing that's legible *during* a run, not just narrated after the
fact in the graveyard.

Open question: is this a presentation change (narrate existing
reputation numbers as guild ranks - no new mechanic, just framing,
similar to idea #4 below) or a genuinely new progression track with its
own thresholds/rewards? The former is low-risk; the latter is new
scope needing the same treatment as #1.

### 7. Cosmetic unit tiers - narrative skin over unchanged math

Idea, well-received in discussion: describe unit stacks narratively
(e.g. "5 units" reads as "an advance formation") without changing any
underlying number. Explicitly presentation-only - the engine still
moves raw integers, `/world/` schema is untouched, nothing here can
violate the golden rule (no generated text ever enters adjudication)
because the skin never feeds back into state. This is the natural
extension of idea #3 (mythic narration) and idea #2 (visuals) applied
specifically to how a garrison count gets described rather than how a
tick's results get summarized.

Lowest-risk idea in this session precisely because it stays entirely on
the narration side of the golden-rule boundary - could be prototyped in
chat narration (as already started) before it's ever worth scripting.

## Format going forward

Append dated entries below as more sandbox sessions turn up ideas. Keep
each entry to: what happened that prompted it, the idea, and the open
questions that would need answers before it's spec-worthy.
