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

**Candidate resolution, surfaced while designing the Guild (idea #8):**
the flow question is hard to answer *because* there's only one resource
in this game - "recurso único: esencia" (E2, frozen). Trade can't be
barter (nothing to barter with) so it's more coherently read as
**tribute, not exchange**: the adventurer gives essence to a force,
one-directional, up to `trade_cap_per_tick: 3`/tick, and gets +2
reputation/tick back - no essence flows the other way. That also
explains why `trade_cap_per_tick` lives in the adventurer's essence
config block instead of the reputation block. Read this way, trade and
`refuge` become a clean pair: refuge is the free/passive route to
reputation (+1/tick, just be present, no cost) and trade is the
paid/active route (+2/tick, faster, costs essence).

**Fully converged shape, after deeper design:**
- **Flat action, not scaled (decided).** Trade isn't "give any amount
  up to 3" - it's a binary action costing exactly 3 essence, paying
  exactly the frozen +2 reputation, every time you take it. Same
  pattern as `fortify` (flat cost per action, not a variable amount) -
  resolves the flat-vs-scaled question without inventing a new number
  or hitting the fractional-reputation trap Bronze almost fell into.
- **Essence genuinely transfers to the force - it doesn't vanish
  (decided).** This matters beyond flavor: `docs/intent.md` explicitly
  names trade as one of the adventurer's "legitimate channels of
  influence" over the war's outcome, alongside quest completion and
  posthumous loot. If the essence were destroyed like recruit/fortify/
  stake costs are (confirmed as the norm - see idea #4's essence-flow
  trace), trade wouldn't be an influence channel at all, just a private
  reputation-farm. The volume cap (3/tick) is what keeps this
  "erosion, not demolition." This makes trade the **second genuine
  transfer** in the whole economy, after loot - everywhere else,
  essence is either minted (yield, quest rewards) or destroyed
  (recruit, fortify, stakes), never moved between ledgers.
- **Positional requirement, tiered by depth into the force's territory
  (decided, illustrative %s not final):** unlike `refuge` ("en
  territorio de F" - anywhere they own), trade requires being present
  somewhere in that force's territory too, but success chance scales
  with how deep you are - ring (outermost, most contested) is riskiest,
  arm is safer, the capital itself is guaranteed:

  | Location | Success chance |
  |---|---|
  | Ring (their side of it) | ~50% |
  | Arm | ~75% |
  | Capital | 100% (guaranteed) |

  Same discipline as Bronze's reputation coin-flip - a seeded formula
  (`hash(seed, tick, adventurer_id, force_id)` against a depth-specific
  threshold), never true randomness.
- **Failure costs the tick, never the essence (decided).** A failed
  trade attempt doesn't burn the 3 essence and doesn't transfer
  anything - the adventurer just spent an order slot that tick for
  nothing. Makes trading from the ring a real, essence-safe gamble
  (skip the trip to the capital, risk wasting the attempt) rather than
  a punishing one.
- **What's exchanged: narrative-only, no new tracked resource
  (decided).** `docs/intent.md`'s single-resource decision ("recurso
  único: esencia") and CLAUDE.md's explicit non-goal ("múltiples
  recursos") rule out real tradeable items - mechanically it's always
  essence. What varies is the *telling*: essence delivered to Force One
  might narrate as disciplined logistics, to Force Three as steel and
  blades - same pattern as idea #7's cosmetic unit skins, zero new
  schema.
- **Refuge, contrasted explicitly**: free (no essence cost), passive
  (+1/tick just for presence), and requires only *any* territory that
  force owns - broader and gentler than trade's capital-specific,
  costed, probabilistic version. Confirmed in the same state as trade -
  `refuge_per_tick` exists in `era.yml`, appears nowhere in the engine.
  The `refuge: 25` threshold this ties to is the same number already
  reused as the Guild's Gold-tier gate (idea #8) - doing double duty.

**Open questions before this is spec-worthy:**
1. The exact success percentages per depth tier (50/75/100 above are
   illustrative, not decided).
2. This needs a genuinely new action in `move.schema.json`'s closed
   catalog - unlike the Guild, which reuses `accept_quest` wholesale,
   nothing like `trade` exists today. Adventurer-only, costs one of
   their 2 order slots.
3. Whether refuge, once actually built, should get the same kind of
   depth/positional richness trade just got, or stay simple as
   originally spec'd (any territory, flat +1/tick, no risk).

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
- **Quest types (decided): two, not three.** `travel` (A→B, with path
  constraints - e.g. neutral-only vs. must-cross-hostile-territory) and
  `hold` (occupy a region for N consecutive ticks, reusing `blockade`'s
  existing consecutive-occupation tracking rather than new state). The
  earlier "scout the three rings" idea folds into `travel` - it's just
  travel quests with different targets, not a third mechanic.
- **`travel` deadlines / `hold` N, per tier (decided): 3/6/10/15 ticks
  to complete a `travel`; 2/4/6/10 ticks to complete a `hold`**
  (Bronze/Silver/Gold/Platinum), same widening-gap shape as every other
  curve here. **Gold and Platinum `hold` additionally require the
  region be actively contested during the hold**, not just occupied -
  Bronze/Silver are pure endurance, Gold/Platinum require real danger
  in the narrative sense (F4 still makes the adventurer mechanically
  safe from ordinary combat regardless - the stakes are narrative
  weight, not literal risk, unless a hunt is explicitly declared).
- **What `hold` means to the forces, stated explicitly: nothing.**
  Confirmed by design, not a gap - same "does not touch force state"
  principle idea #1 started with. The region's ownership, combat, and
  yield all proceed completely independent of the adventurer's
  presence (the same F4 coexistence rule that lets them stand unharmed
  in a warzone). The moment `hold` started actually helping whichever
  force owns that ground, it would reopen the power-ceiling tension
  "helping conquest" ran into below.
- **"Helping conquest" -> reframed as "raid the ruins," explicitly not
  a new map location.** The original idea (adventurer meaningfully
  assists a force's conquest) was flagged as a real tension with the
  frozen power-ceiling boundary - the adventurer's ceiling is
  specifically verified by counterfactual replay to guarantee they
  never decide who wins territory, so a quest type that gives them real
  combat/conquest weight isn't a small addition. Reframed instead as
  **dungeon-flavored quests layered onto the *existing* 9 neutral
  regions** - no new map nodes, which would reopen the frozen M1
  decision ("12 regiones... congelado") and the map generator's
  rotational-isomorphism test. Flavor text varies by who currently owns
  (or doesn't own) that region - free to implement, since ownership is
  already tracked, no new schema needed for the flavor itself.
- **Narrative-choice quests: a real mechanic, not just flavor, still to
  be designed in full.** Instead of "stand still for N ticks," a
  `hold`/dungeon-flavored quest could unfold as a story with real
  junctures - a choice at some point that can lose the quest outright,
  not just a duration timer. Stays inside the golden rule cleanly: the
  *prose* at each juncture is generated/lore-register (already how idea
  #3 wants results narrated), but the *pass/fail consequence* of a
  choice must be a fixed rule decided in advance or a seeded flip (same
  discipline as Bronze's reputation coin-flip) - never an LLM deciding
  in the moment whether a choice worked. This is probably the strongest
  lever yet for making guild quests feel like *playing* rather than
  *waiting* - not yet designed further than the mechanism being
  compatible.
- **Scope note, explicit:** the depth here is intentional, not
  something to trim - discussed directly and the answer was to keep it
  and handle the size through *implementation phasing* instead (Bronze
  + Silver first, prove it out, then the rest - one phase at a time,
  same discipline as everything else this engine was built with), not
  by cutting the design down now. Worth remembering when this eventually
  moves toward `docs/intent.md` - it should land as several small PRs,
  not one.
- **Four tiers (decided): Bronze (entry-level) → Silver → Gold →
  Platinum.** Deliberately non-linear/widening at every axis below, so
  Platinum reads as heroic rather than "Gold with a bigger number."
- **Rank: per-force (decided)** - three separate standings, not one
  global ladder, since reputation is already tracked per-force and rank
  reads off tier completions at that specific capital: **rank = the
  highest tier completed there.** No separate rank counter needed.
- **Tier access gates on existing per-force reputation (decided)** -
  reuses `era.yml`'s thresholds rather than inventing a parallel trust
  score: Silver needs `trade: 10`, Gold needs `refuge: 25` (both
  already-frozen numbers, now doing double duty). Platinum gets a new
  threshold on the same widening curve - **reputation ≥ 70** with that
  force (curve considered: 0/10/25/45 vs /55 vs /70; 70 was chosen as
  the steep option, gaps of 10/15/45).
- **Reputation reward per tier (revised after sandbox testing): Bronze
  is probabilistic, Silver/Gold/Platinum stay flat at 1 / 5 / 15.**
  Originally decided as a flat 0 for Bronze ("the doing of it is the
  point, not the reward") - but that turned out to create a real
  circularity, caught by testing rather than reasoning about it on
  paper: with `refuge_per_tick`/`trade_per_tick` both confirmed inert
  in the engine (idea #5), flat-0 Bronze meant **no path from 0
  reputation to Silver's 10-threshold existed at all.** Fixed with a
  seeded coin-flip, not true randomness (per the determinism rule -
  same discipline as F2's collision-order hash): each Bronze completion
  computes `hash(seed, tick, adventurer_id, quest_id)` parity - on a
  hit, +1 reputation; on a miss, +0. Gaps from Silver up (1, 4, 10)
  still widen sharply, same "heroic, not linear" shape as the access
  thresholds.
- **Essence reward per tier (Bronze revised, Silver/Gold/Platinum
  unchanged): 1(or 2) / 3 / 8 / 25.** Silver/Gold/Platinum unchanged.
  Bronze's essence reward is now **conditional on the same coin-flip**:
  1 essence if the flip hit (reputation gained that completion), 2 if
  it missed - also caught by sandbox testing: a flat 1-essence reward
  against a 1-essence stake made Bronze exactly break-even whenever the
  coin-flip missed, which read as busywork rather than "something to
  do." Doubling the consolation essence keeps every completion net-
  positive regardless of the flip (expected value +0.5 essence/
  completion averaged over both outcomes). Silver/Gold/Platinum's
  reward field is fine as originally set - the existing quest schema's
  `reward` field is essence (exactly how `raid`/`blockade`/`attrition`/
  `dethrone` already pay out, no reputation attached), guild quests get
  essence via that same field *plus* the reputation mechanic above.
  Platinum's 25 sits above every existing rubber-band reward
  (`dethrone`'s 15 is the current ceiling) - deliberate, meant to be
  the hardest thing to pull off in the game.

**Sandbox trial (2026-07-24, 2 Bronze `travel` completions tested):**
both coin-flips missed (reputation stayed 0/0/0 - a real possible
outcome at 50/50 over only 2 trials, not a bug), but the doubling fix
meant essence still went 5 → 6 net across both, confirming the fix
does what it's supposed to: even on a bad-luck streak the adventurer
gains something, never just breaks even. Two misses running is also a
fair warning that reputation can plausibly take a genuine while to get
moving under pure chance - a real property of this design, not
necessarily a problem, but worth knowing before it's frozen. Not yet
tested: an actual coin-flip hit, or anything at Silver tier or above.

**Sandbox trial (2026-07-24, continued): Silver/Gold/Platinum, all
three, bootstrapped rather than earned.** Since Silver/Gold/Platinum
were never random (only Bronze got the coin-flip fix), testing them is
deterministic by construction - the only thing that needed a shortcut
was *reaching* the thresholds, so reputation and (for Platinum) force-3's
territory were set directly rather than played into, same transparent
approach as the earlier position teleport. Confirmed working: the
schema stayed fully valid through every bootstrap (checked via
`load_state` after each step) since only already-existing fields were
touched, nothing needed inventing to make it validate. Results: Silver
(stake 1, essence 5→8, reputation 10→11), Gold (stake 2, essence
8→14, reputation 25→30), Platinum (stake 2, essence 12→37, reputation
70→85) - rank read cleanly off "highest tier completed" at each step,
no separate counter needed anywhere.

Two real findings, both edge cases the design didn't have an answer for
yet:
- **Capability-unlock ambiguity with multiple forces.** All three tiers
  fired a "first-ever" unlock in this trial because force-3 was the
  adventurer's only relationship so far - untested: reaching Gold with
  force-3 *after* already holding Gold with force-1. Does that fire a
  second unlock, or does "first time reaching a tier" mean the *very*
  first time across all three forces, ever, full stop? Genuinely
  undecided, not just unbuilt.
- **Platinum's two gates might rarely coincide in real play.** Needing
  both reputation ≥70 *with a specific force* and *that same force*
  reduced to one region is a real double condition - in this trial both
  were set by hand, so it proved the *math* works, not that the
  *situation* is reachable at a rate that feels right. Worth watching
  in real play whether Platinum ends up almost never triggering, versus
  exactly as rare as intended.
- **Stakes: reuse the existing two sizes (decided)** - Bronze/Silver
  charge the `minor` stake (1), Gold/Platinum the `major` stake (2).
  No new stake tiers invented.
- **No penalty on failure, expiry, or abandonment (decided)** - a
  `hold` quest broken by a hunt, or any guild quest left unclaimed past
  its deadline, just fizzles like an unclaimed rubber-band quest
  already does. Only the stake is at risk, never reputation - punishing
  an attempted heroic rescue on top of the resources already spent
  would discourage ever reaching for Platinum at all.
- **Platinum's "heroic condition" (decided): a force reduced to a
  single region.** This is the one guild quest type tied to a genuine
  world-state trigger rather than pure difficulty scaling - the guild
  reacting to a force in real crisis, generated the same way the
  rubber-band engine already reacts to a force approaching dominance
  (opposite condition, same mechanism: a deterministic state trigger,
  not a force requesting help - staying clear of "encargos" even here).
- **Rank reward: capabilities - revised into a richer system, supersedes
  the earlier "flat schema" reading.** `docs/intent.md`'s "Crecimiento"
  row defines capabilities as discrete unlocks, each a new schema
  action, currently completely unused (`capabilities: []` always,
  nothing ever fills it) - that part stands. What changed: capabilities
  are no longer one-per-tier, they're **one per (tier, force) pair** -
  each force's chapter grants its own flavored variant of the tier's
  capability (Force One's Gold differs mechanically-in-flavor from
  Force Three's Gold), so reaching a tier with multiple forces unlocks
  multiple distinct capabilities at that tier, not duplicates of one.
  This explicitly reopens the earlier "flat list, no new schema shape"
  simplification - `capabilities` now needs to track *learned* vs
  *equipped* separately, which a flat array can't represent on its own.
  **Full mechanic:**
  - **Eligibility vs. possession**: reaching a tier with a force makes
    you *eligible* to learn that force's variant - it does not grant it
    automatically. Learning costs essence, paid per variant, per force
    - learning force-1's Gold and force-3's Gold are two separate
      purchases, full price each, no discount for already owning "a"
      Gold-tier capability from elsewhere.
  - **Learning cost (decided, separate curve from the reward table):
    5 / 15 / 40** for Silver/Gold/Platinum - deliberately steeper than
    the 3/8/25 reward numbers, since a capability is a standing
    upgrade, not a one-time payout. Bronze grants no capability at all
    (nothing to learn there, consistent with Bronze's "the doing is the
    point" framing throughout).
  - **Equip slots, one per tier (Silver/Gold/Platinum)**: only one
    capability active per slot at a time. Normally a slot only accepts
    a capability of its own tier, but you can freely swap between any
    *already-learned* variants of that tier (any force) - nothing locks
    you out of capabilities you've paid for.
  - **Platinum's slot is the exception**: it accepts *any* learned
    capability, any tier, any force - the capstone reward is
    flexibility, not raw power.
  - **Switching costs too, every time, not just the first swap**: half
    the learning price of whichever capability you're switching *into*
    - roughly 3 / 8 / 20 to re-equip within Silver/Gold/Platinum
    (applies the same way switching into Platinum's wildcard slot -
    half of whatever tier you're bringing in, not a separate Platinum-
    specific number). Specialize in one variant and never pay a switch
    fee, or diversify across forces and pay both to learn and to keep
    reconfiguring - a real, ongoing essence sink either way.
  - **Tier → capability mapping (decided)**: Silver = a second
    concurrent quest slot; Gold = fast-travel (2 regions per move
    instead of 1); Platinum = "sanctuary," temporary hunt-immunity.
    Escalating utility → mobility → survival, matching each tier's
    narrative weight.
- **Numbers are all first-pass, not final** - the plan is to run them
  in the sandbox and tune whatever feels off before any of this goes
  near `docs/intent.md`.

**Open questions before this is spec-worthy:**
1. The new `docs/intent.md` "Fuentes" table row this needs, and the
   real schema surface this now implies for the adventurer entity -
   which quests completed where (rank is derived from this, still
   needs storing), which (tier, force) capabilities are learned, and
   which one is currently equipped per slot. Meaningfully more than the
   flat `capabilities: []` array can hold today.
2. Narrative-choice quests need real design, not just a compatible
   mechanism - how many junctures, how choices map to pass/fail, how
   much is fixed-in-advance vs. seeded-per-attempt.
3. `max_claimants` for guild quests - exclusive (`1`, seeded-collision
   winner takes it, confirmed as the intended model) vs. `open` - which
   one, and does it vary by tier.

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

### 10. Fortify escalation + upkeep, and a new `siege` mechanic

Prompted by watching fortification become a solved wall in the
sandbox trial - `ring-1` and `ring-3` both hit the level-3 cap and,
once garrisoned, needed genuinely overwhelming numeric advantages to
break in a single `attack_region` (only that one big three-way
collision actually cracked one). Two changes, converged:

**Fortify: escalating cost and bonus, plus upkeep-or-erosion
(illustrative numbers, not final):**

| Level | Cost (was flat 5) | Cumulative bonus (was flat +2/level) | Upkeep/tick |
|---|---|---|---|
| 1 | 5 | +2 | 1 |
| 2 | 10 | +5 | 3 |
| 3 | 20 | +10 | 6 |

Both cost and bonus escalate now, not just cost - level 3 is a
genuinely bigger commitment for a genuinely bigger payoff, not "more of
level 1." New: **upkeep, paid every tick or the fortification erodes**
(one level lost per tick of missed payment, proposed) - distinct from
idea #4's general unit-upkeep proposal, but the same underlying fix:
essence sinks that scale with what's already held, not just one-time
purchases. Worth remembering while designing this: confirmed (idea #4)
that garrison size has no cap anywhere in the schema, fortified or not
- fortification level and raw unit count are two totally uncapped,
unrelated axes today.

**`siege`: a new multi-tick action that eats fortification faster, at
a premium.**
- Erodes fortification over several ticks (proposed: -1 level every
  2-3 ticks) rather than requiring one overwhelming `attack_region` -
  meant specifically to give heavily-fortified positions a counter
  that isn't just "more units than they have."
- Costs extra, every tick the siege continues (not a one-time fee) -
  additional essence or units committed specifically to the siege
  ("siege machines," narrative flavor only, same as trade's narrative-
  only goods - no new tracked resource).
- **Explicit design stance on external interference, recommended and
  agreed: no special isolation.** A siege doesn't lock the target region
  in a bubble - it's a standing *commitment by the attacker* (their
  units stay engaged, tied up, unavailable elsewhere), not a shield
  around the defender. The defender can still reinforce or fortify
  normally; other forces and the adventurer aren't frozen out either.
  This was chosen deliberately over a special-cased isolated state,
  because everything else in this engine resolves through the same
  simultaneous-commitment machinery every tick (Diplomacy model) - a
  "nothing else can touch this" rule would be a real consistency break
  for no clear benefit. The actual cost of sieging is the strategic
  exposure it creates elsewhere on the board while your army's tied
  down, not an artificial lockout. Bonus: this means a Guild `hold`
  quest at Gold/Platinum (already requires contested ground) can
  naturally coincide with a live siege with zero new rule needed - the
  intersection falls out of mechanics that already exist.

**Open questions before this is spec-worthy:**
1. All numbers above are illustrative/first-pass - cost/bonus/upkeep
   curve for fortify, erosion rate and premium cost for siege.
2. Exact erosion consequence for missed fortify upkeep - one level
   per missed tick was proposed, not confirmed as final.
3. `siege` needs a new `move.schema.json` entry (force-only) and state
   to track an in-progress siege across ticks (which region, which
   attacker, ticks elapsed, erosion accumulated).
4. Relationship to idea #4's general unit-upkeep proposal - fortify
   upkeep and unit upkeep are being designed as two separate costs;
   worth checking they compose sensibly rather than fighting each
   other once both exist.

### 11. Decree — a category of infrequent, high-impact force actions

Prompted directly by fortify/siege's new upkeep costs (idea #10):
once units and fortification both cost something ongoing to maintain,
a force needs a real lever for *shedding* what it can't afford, not
just accumulating. "Decree" is the name for a category of special
force actions distinct from routine orders - dismissal and surge
recruitment are the first two, more could join later (same pattern as
"quest" being a category with multiple types).

**Dismissal (decided): a force voluntarily reduces its own unit count,
no refund.** Purely a release valve for upkeep pressure - matches
every other spend in this economy (recruit, fortify, stakes) being
one-directional, never returned.

**Surge recruitment (converged shape):**
- Doubles the units obtained from a recruit order. The normal per-unit
  essence cost and the resulting units' upkeep are both **unaffected**
  - decree only changes what you get from the action, not its ongoing
  cost once recruited.
- What actually costs extra: a **flat surcharge for invoking decree
  itself**, on top of normal recruit cost, that **escalates with
  consecutive use and resets to base the moment a tick passes without
  using it** - "punish spam, forgive restraint" (confirmed framing).
  Illustrative curve: surcharge 5 → 10 → 20 on back-to-back uses,
  drops to 5 on the first skipped tick. Same widening-gap shape as
  every other escalating curve in this session.

**Open questions before this is spec-worthy:**
1. All numbers illustrative (surcharge curve, reset condition - resets
   after exactly one skipped tick as proposed, not confirmed as a
   longer cooldown).
2. Needs new `move.schema.json` entries (force-only) - likely a
   `decree` action with a `kind: dismiss | surge_recruit` parameter,
   or two separate actions; not decided.
3. Interaction with idea #4/#10's upkeep proposals - dismissal only
   makes sense once *something* costs upkeep (units and/or
   fortification); sequencing matters if these get built separately.

### 12. Agent client gap: forces aren't actually told what their actions do

Real finding in already-built code, not a design idea - checked
directly rather than assumed. `agent_client/prompt.py`'s system prompt
never describes what `move_units`/`attack_region`/`recruit`/`fortify`/
etc. actually *do* - it only explains the propose_orders/validation
mechanics generically. `schema/move.schema.json` has exactly one
`description` field in the entire file (on the top-level batch format),
none on any individual action definition. So today, a force's LLM has
to infer what each action means purely from field names and the tool's
JSON-shape - very different from the sandbox trials in this session,
where every subagent prompt had hand-written prose rules (F1 combat
math, action preconditions, etc.) standing in for something the real
client doesn't do yet.

**Fixed (2026-07-24)**: added a `description` to `order` and to all
seven action definitions in `schema/move.schema.json`, grounded in
`docs/intent.md`'s catalog and verified line-by-line against the actual
phase code rather than assumed - this caught two inaccuracies before
they shipped: `attack_region`'s `target: adventurer` description
initially claimed a direct reputation penalty on the killer, but
`config.py`/`era.yml` have no such parameter at all - what's actually
implemented (confirmed in `phase9_spawn.py`) is a vengeance quest spawn
against the killer, a different and more indirect mechanism, and the
description was corrected to match. `claim_loot`'s description
similarly claimed a partial-value discrepancy that doesn't exist - the
code confirms the claimant always gets the pot's full value. Verified
end-to-end: `agent_client/llm.py`'s `_orders_tool_schema` passes these
descriptions straight through to what the model actually sees in the
tool-use call, no code changes needed there; full suite (154 tests)
still passes, schema still validates as proper JSON Schema.

## Pending topics, not yet discussed

- Force actions (general reconsideration, scope not yet stated)

## Format going forward

Append dated entries below as more sandbox sessions turn up ideas. Keep
each entry to: what happened that prompted it, the idea, and the open
questions that would need answers before it's spec-worthy.
