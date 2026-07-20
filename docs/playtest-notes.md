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

### 8. The Adventurers' Guild — per-force rank ladder + capability rewards

**Supersedes idea #1.** Started as "give the adventurer a small always-
available quest," grew through discussion into a full guild system once
it became clear a single `personal_quest` reframe (the option this doc
originally leaned toward) couldn't carry varied quest types, multiple
locations, and a rank ladder - `personal_quest` is also confirmed inert
in the current engine (grepped: set once at spawn in `phase2_spawn.py`,
never read again anywhere). The guild needs real machinery either way,
so it's shaped to reuse what already exists rather than invent new
state.

**Converged shape:**
- **Source**: a 4th deterministic quest source, alongside the rubber-
  band engine and world-event triggers - reuses the existing
  `quests/active/` schema and `accept_quest` action, `eligibility:
  adventurer` only.
- **Explicitly not "encargos"**: `docs/intent.md` defers "fuerzas como
  emisoras de encargos" to v2 on purpose, and there's already a
  reputation threshold (`errands_v2: 40`) reserved for it. The guild
  authors quests deterministically; forces never choose or issue them,
  even though boards are located at each force's capital and may be
  persona-flavored.
- **Location**: one guild, a board at each of the 3 capitals. Quests
  generated per `(seed, tick, force_id)`, same seeding discipline as
  everything else - gives the adventurer a real reason to visit all
  three corners of the map, not just the one they spawned near.
- **Quest type candidates** (not finalized): travel A→B with path
  constraints (e.g. neutral-only vs. must-cross-hostile-territory);
  bodyguard / hold-a-region-for-N-ticks (can likely reuse `blockade`'s
  existing consecutive-occupation tracking rather than new state);
  scout-the-three-rings.
- **Reward hook**: completing a quest at force X's capital nudges
  reputation *with* force X - reuses the existing per-force
  `reputation.deltas` mechanism, no new score invented.
- **Rank: per-force (decided)** - three separate standings, not one
  global ladder. Chosen because reputation is already tracked per-force
  in the frozen design, so per-force rank reads off something that
  already exists rather than requiring a new aggregate.
- **Rank reward: capabilities (decided)** - `docs/intent.md`'s
  "Crecimiento" row already defines capabilities as discrete unlocks,
  each a new schema action, currently completely unused (every
  adventurer spawns with `capabilities: []`, nothing ever fills it).
  Candidate unlocks, none chosen yet: a fast-travel order (2 regions in
  one move instead of 1); a "sanctuary" capability granting temporary
  hunt-immunity; a second concurrent quest slot.

**Open questions before this is spec-worthy:**
1. Exact quest catalog - concrete mechanics per type, plus real
   reward/stake/deadline numbers (none invented here, per the stop
   rule).
2. How rank is actually computed at a given capital - a raw reputation
   threshold, a separate completions counter, or both together.
3. Rank tier names and count, and which tier unlocks which capability.
4. The new `docs/intent.md` "Fuentes" table row this needs, and the
   adventurer schema fields to carry per-force rank/progress
   (`world.schema.json`'s `adventurer` def would need new fields beyond
   today's flat `reputation` map).

### 9. The Strategist — force-hireable deterministic intel subscription

Prompted by a proposal to let forces "remove some fog of war" for a
price. Flagged immediately: fog of war isn't just unbuilt in v1, it's
an explicit non-goal (`docs/intent.md` boundaries: "Niebla de guerra →
v2"), and the "Información" row makes v1 perfect-information for
everyone on purpose - there's no fog to partially sell back. The one
thing genuinely hidden today is rival *personas*, deliberately kept
secret as a zero-cost theory-of-mind signal ("señal de teoría de mente
a costo cero"); a mechanic that lets a force buy insight into a rival's
temperament instead of inferring it from behavior would compete
directly with the capability the project exists to measure - flagged as
a real tension, not a small compatibility question, per CLAUDE.md's
rule that every new mechanic must justify itself as a measurable
capability signal or be rejected.

**Landed instead on a version that reveals nothing hidden**: intel
derived entirely from data that's already public.

**Converged shape:**
- A force-only action (name TBD - `hire_strategist` as a placeholder)
  that, while active, adds a deterministic "situation report" covering
  *both* rival forces to the hiring force's own context for its next
  tick's decision.
- Report contents must be a **fixed, deterministic catalog** - the same
  rigor as F1-F4, not "AI judgment about the enemy." Candidates:
  aggression rate (attacks per tick over a trailing window), recent
  win/loss ratio, momentum (territory delta over N ticks), weakest
  currently-held region by defense power. All computable today from
  `/moves/` history that's already public - nothing new gets revealed,
  it's pre-digested.
- **Stays inside both frozen rules**: the golden rule (report is
  precomputed data, not an LLM judgment, and never touches
  adjudication) and "una invocación LLM por tick emite todas las
  órdenes" (the report feeds the force's *existing* single per-tick
  call - no second agent, no separate strategist LLM).
- **Timing**: hiring this tick can't inform this tick's own orders
  (same-batch simultaneous submission) - the report can only land for
  the *next* tick. That naturally makes this a standing/recurring cost
  rather than a one-shot purchase, which fits "priced high so it's used
  wisely" better than a single toggle.

**Open questions before this is spec-worthy:**
1. The exact per-tick cost (none invented here).
2. Persists until cancelled, or expires after N ticks and needs
   renewing?
3. The final report-contents catalog - which heuristics, exact
   formulas, not just the candidate list above.
4. The new `move.schema.json` catalog entry, plus where the report
   itself is carried in `world/forces/<id>.yml` between ticks.

## Format going forward

Append dated entries below as more sandbox sessions turn up ideas. Keep
each entry to: what happened that prompted it, the idea, and the open
questions that would need answers before it's spec-worthy.
