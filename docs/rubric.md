# Mythic Engine — Eval Rubric (v1)

Inventory item 8 from `docs/intent.md`: the eval rubric, defined before
the first era. `docs/intent.md` stays the frozen design spec; this
document is downstream of it and does not add or change any game rule,
formula, or parameter. Every dimension below is grounded in a metric or
gap `docs/intent.md` already names — nothing here is invented from
scratch.

## Scope

What this scores: each of the three LLM-driven forces' capability
signal across one completed era, computed only from committed
artifacts — `/moves/` and `/chronicle/`, exactly the pair
`docs/intent.md` names as the dataset (`/lore/` excluded by
construction). No additional instrumentation; the harness reads the
repo post-era, same as everywhere else in this project.

## Non-goals

- **Not a leaderboard.** Supremacy is an outcome of the mechanics'
  rubber-band counterweight plus the other two forces' play, not a
  clean capability signal by itself — see Dimension 2.
- **Not a verdict on the adventurer.** The adventurer's power ceiling is
  a permanent calibration constraint, verified by counterfactual
  replay, not a subject this rubric scores.
- **Not a resolution of the open knowledge gaps** (rubber-band
  intensity, n=3 collusion risk, combat exchange rate, permadeath's
  effect on human participation). Those stay open questions this
  rubric surfaces as diagnostics — see below — never as scored
  pass/fail criteria. Treating an open knowledge gap as a scored axis
  would be inventing an answer the design doc explicitly hasn't
  reached yet.

## Dimensions

### 1. Mechanical competence (validity rate)

**Metric:** fraction of ticks in the era where the force's own move
batch was accepted without NPC substitution (chronicle "Órdenes"
table's `estado` column and the `Sustituciones` line).

**Grounding:** the Effects gap's "% ticks NPC por era como health
check," applied per force rather than as an era-wide aggregate.

**Read as:** baseline competence at operating the interface at all. A
tick where the NPC policy played instead of the agent cannot be scored
on any other dimension that tick — there is no agent decision to
measure.

### 2. Strategic trajectory (economic + territorial)

**Metric:** essence and region-count trend across the era (chronicle
"Economía" and "Supremacía" tables), plus whether the force ever
triggered a rubber-band quest against itself (a "Quests" spawn event
with that force as the leader in the trigger).

**Grounding:** the rubber-band engine exists specifically to test
sustained-dominance play. Being targeted by it is a capability signal
— the force is winning enough to draw pressure — not a penalty.

### 3. Combat discipline

**Metric:** win/loss ratio across the era's F1 resolutions (chronicle
"Combates" table), and the rate of mirrored all-in attacks (chronicle
"Colisiones" table) relative to their outcomes.

**Grounding:** F2's own commentary — "el all-in es apuesta real; señal
de gestión de riesgo." Mirrored attacks are explicitly a risk-
management signal, not inherently good or bad; this dimension records
the pattern and its outcome rather than scoring risk appetite itself.

### 4. Adversarial responsiveness

**Metric:** change in a force's order-type distribution in the tick(s)
immediately following a rubber-band quest resolving against it, versus
its baseline distribution earlier in the era.

**Grounding:** this is the closest proxy to the project's actual
purpose — the Alignment gap's rule that "cada mecánica nueva se
justifica como señal medible de capacidad de agente." A force that
never changes behavior under pressure is not demonstrating adaptive
capability regardless of its win rate.

### 5. Persona fidelity (behavioral distinctiveness)

**Metric:** do the tendencies described in that force's
`personas/force-N.md` (aggression frequency, territorial patience,
risk appetite) actually show up as a distinguishable pattern in its
order history, compared to the other two forces operating under the
identical ruleset?

**Grounding:** "simetría mecánica, asimetría de persona... divergencia
de resultados atribuible al agente, no a las reglas." This dimension
checks whether the project's own core premise held for that era — it
is not grading the agent against an external ideal of good play.

**Explicitly not automatable in v1.** Mechanics are symmetric by
construction, so this requires a human reading the chronicle and the
persona side by side. Scripting it is future work, gated on having
played eras to check the read against, not on anything in this repo
today.

### 6. Cost efficiency

**Metric:** tokens spent per tick against `world/era.yml`'s
`budget.tokens_per_era`, once that field is set to a real, non-zero
value for the era being scored.

**Grounding:** the Effects gap's "costos de inferencia sin
presupuestar." `budget.tokens_per_era` is still `0` (uncapped) as of
the tracer-bullet era; this dimension is inert until era.yml sets a
real value, by design.

## Diagnostics tracked, not scored

These stay open per the Knowledge gap and must not be treated as
pass/fail criteria until enough played eras exist to calibrate them:

- Tacit collusion between two forces against the third (the n=3
  collusion risk).
- Adventurer life expectancy (the permadeath-without-inheritance
  calibration question).
- The counterfactual delta from the adventurer's post-era NPC-
  substituted replay ("techo verificable") — reported, used to tighten
  adventurer caps in `era.yml`, never used to score a force's play.

## Reporting

One rubric pass per completed era. Dimensions 1, 2, 3, and 6 are
mechanical and can eventually be scripted straight from `/moves/` and
`/chronicle/`; dimensions 4 and 5 need a human reading both against the
personas. Output is descriptive per dimension, not a single aggregate
score — collapsing six dimensions and three open diagnostics into one
number would hide exactly the disagreements (e.g., high validity but
low persona fidelity) this rubric exists to surface.

## Status

Defined before era 1, per `docs/intent.md` inventory item 8. This
document is itself subject to the same knowledge-gap calibration as
the rest of v1 — revisit after era 1 completes.
