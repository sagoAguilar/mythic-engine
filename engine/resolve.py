"""The deterministic arbiter entry point.

``resolve(state_dir, moves_dir, seed)`` loads the world from
``state_dir/world/`` (the directory layout frozen in docs/intent.md),
consumes the move files in ``moves_dir``, runs the 11 resolution phases
in their frozen order — applying each phase's delta to the working
state before the next phase runs — and writes the next-tick state and
``state_dir/chronicle/tick-<N>.md`` in place. The GitHub Actions
workflow is a thin shell around this call; everything here is pure
Python, offline, and byte-deterministic: same state + same moves +
same seed = same output tree.

Wiring decisions owned by the resolver, not the phases:

- **Spawn carve-out**: phase 1 ignores batches from unknown actors, but
  spawn_adventurer is the one move with no prior entity. Schema-valid,
  correctly-ticked batches from not-yet-living adventurer actors that
  contain a spawn order are injected into the effective batch list
  (duplicates dropped wholesale, the single code path's spirit).
- **Transient working-state keys**: ``pending_combats`` (phase 4 → 5),
  ``adventurer_deaths_this_tick`` (phases 5/8 → 9), ``tick_events``
  (everything → 11). All stripped before the final state is written.
- **Cached force unit totals** are recomputed at assembly from region
  garrisons, per the phase-3/4 contract.
- **The arbiter is caged**: the assembled next state is validated
  against schema/world.schema.json before a single byte is written.
- **Cataclysm is not a tick**: phase 10's coronation/era-end flags ride
  the chronicle; era transition is separate tooling.

No wall clock, no network, no ``random`` — the only randomness anywhere
is the seed chain inside the phases.
"""

import copy
import shutil
from pathlib import Path

import yaml

from engine.config import load_era_config
from engine.phase1_validation import resolve_validation
from engine.phase2_spawn import resolve_spawn
from engine.phase3_recruit_fortify import resolve_recruit_fortify
from engine.phase4_movement import resolve_movement
from engine.phase5_combat import resolve_combat
from engine.phase6_claim_loot import resolve_claim_loot
from engine.phase7_yield import resolve_yield
from engine.phase8_quests import resolve_quests
from engine.phase9_spawn import resolve_quest_spawn
from engine.phase10_supremacy import resolve_supremacy
from engine.phase11_chronicle import resolve_chronicle
from engine.validate import ValidationError, validate_move, validate_world


def _load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_dir(directory: Path) -> dict:
    if not directory.exists():
        return {}
    return {p.stem: _load_yaml(p) for p in sorted(directory.glob("*.yml"))}


def load_state(state_dir: Path) -> dict:
    """Assemble the world document from the directory layout."""
    world = state_dir / "world"
    entities = _load_dir(world / "forces")
    graveyard_dir = world / "graveyard"
    graveyard = (
        [_load_yaml(p) for p in sorted(graveyard_dir.glob("*.yml"))]
        if graveyard_dir.exists() else []
    )
    state = {
        "era": _load_yaml(world / "era.yml"),
        "tick": int((world / "tick.txt").read_text(encoding="utf-8").strip()),
        "combats_last_tick": _load_yaml(world / "combats_last_tick.yml") or [],
        "regions": _load_dir(world / "regions"),
        "forces": {k: v for k, v in entities.items() if not k.startswith("adventurer-")},
        "adventurers": {k: v for k, v in entities.items() if k.startswith("adventurer-")},
        "quests": {
            "active": _load_dir(world / "quests" / "active"),
            "resolved": _load_dir(world / "quests" / "resolved"),
        },
        "graveyard": graveyard,
        "supremacy": _load_yaml(world / "supremacy.yml"),
    }
    validate_world(state)
    return state


def write_state(state_dir: Path, state: dict, chronicle: str) -> None:
    """Write the next-tick state tree; era.yml is never rewritten."""
    world = state_dir / "world"
    for sub in ("regions", "forces", "quests/active", "quests/resolved", "graveyard"):
        directory = world / sub
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)

    def dump(path: Path, data) -> None:
        path.write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")

    (world / "tick.txt").write_text(f"{state['tick']}\n", encoding="utf-8")
    dump(world / "combats_last_tick.yml", state["combats_last_tick"])
    dump(world / "supremacy.yml", state["supremacy"])
    for region_id, region in state["regions"].items():
        dump(world / "regions" / f"{region_id}.yml", region)
    for force_id, force in state["forces"].items():
        dump(world / "forces" / f"{force_id}.yml", force)
    for adventurer_id, adventurer in state["adventurers"].items():
        dump(world / "forces" / f"{adventurer_id}.yml", adventurer)
    for status in ("active", "resolved"):
        for quest_id, quest in state["quests"][status].items():
            dump(world / "quests" / status / f"{quest_id}.yml", quest)
    for entry in state["graveyard"]:
        name = f"{entry['id']}-e{entry['era']}-t{entry['died_tick']}.yml"
        dump(world / "graveyard" / name, entry)

    chronicle_dir = state_dir / "chronicle"
    chronicle_dir.mkdir(parents=True, exist_ok=True)
    (chronicle_dir / f"tick-{state['tick']}.md").write_text(chronicle, encoding="utf-8")


def _spawn_carveout(raw_moves: list, state: dict, config, tick: int) -> list[dict]:
    """Schema-valid spawn batches from not-yet-living adventurer actors."""
    known = set(state["forces"]) | set(state["adventurers"])
    candidates: list[dict] = []
    for batch in raw_moves:
        if not isinstance(batch, dict):
            continue
        actor = batch.get("actor")
        if not isinstance(actor, str) or not actor.startswith("adventurer-"):
            continue
        if actor in known:
            continue
        try:
            validate_move(batch, config)
        except ValidationError:
            continue
        if batch.get("tick") != tick:
            continue
        if any(o.get("action") == "spawn_adventurer" for o in batch["orders"]):
            candidates.append(copy.deepcopy(batch))
    counts: dict[str, int] = {}
    for batch in candidates:
        counts[batch["actor"]] = counts.get(batch["actor"], 0) + 1
    return sorted(
        (b for b in candidates if counts[b["actor"]] == 1),
        key=lambda b: b["actor"],
    )


def resolve(state_dir, moves_dir, seed: int) -> dict:
    """Resolve one tick in place. Returns the new state document."""
    state_dir, moves_dir = Path(state_dir), Path(moves_dir)
    config = load_era_config(state_dir / "world" / "era.yml")
    state = load_state(state_dir)
    tick = state["tick"] + 1

    raw_moves = []
    if moves_dir.exists():
        for path in sorted(moves_dir.glob("*.yml")):
            try:
                raw_moves.append(yaml.safe_load(path.read_text(encoding="utf-8")))
            except yaml.YAMLError:
                raw_moves.append(None)  # unparseable: phase 1 ignores it

    # phase 1: schema validation + NPC substitution
    p1 = resolve_validation(state, raw_moves, config, seed)
    batches = sorted(
        p1["batches"] + _spawn_carveout(raw_moves, state, config, tick),
        key=lambda b: b["actor"],
    )

    working = copy.deepcopy(state)

    # phase 2: spawn_adventurer
    p2 = resolve_spawn(working, batches, config, seed)
    working["adventurers"].update(copy.deepcopy(p2["spawned"]))

    # phase 3: recruit, fortify (pre-tick essence)
    p3 = resolve_recruit_fortify(working, batches, config, seed)
    for force_id, change in p3["essence_changes"].items():
        working["forces"][force_id]["essence"] += change
    for region_id, change in p3["unit_changes"].items():
        working["regions"][region_id]["units"] += change
    for region_id, change in p3["fortification_changes"].items():
        working["regions"][region_id]["fortification"] += change

    # phase 4: simultaneous movements and attacks
    p4 = resolve_movement(working, batches, config, seed)
    for region_id, change in p4["unit_changes"].items():
        working["regions"][region_id]["units"] += change
    for region_id, owner in p4["owner_changes"].items():
        working["regions"][region_id]["owner"] = owner
    for adventurer_id, position in p4["adventurer_moves"].items():
        working["adventurers"][adventurer_id]["position"] = position
    working["pending_combats"] = p4["pending_combats"]

    # phase 5: combat resolution
    p5 = resolve_combat(working, batches, config, seed)
    del working["pending_combats"]
    for region_id, change in p5["unit_changes"].items():
        working["regions"][region_id]["units"] += change
    for region_id, owner in p5["owner_changes"].items():
        working["regions"][region_id]["owner"] = owner
    for force_id, change in p5["essence_changes"].items():
        working["forces"][force_id]["essence"] += change
    for region_id, loot in p5["loot_changes"].items():
        working["regions"][region_id]["loot"] = loot
    for death in p5["adventurer_deaths"]:
        del working["adventurers"][death["id"]]
    working["graveyard"].extend(copy.deepcopy(p5["graveyard_additions"]))

    # phase 6: claim_loot
    p6 = resolve_claim_loot(working, batches, config, seed)
    for adventurer_id, change in p6["essence_changes"].items():
        working["adventurers"][adventurer_id]["essence"] += change
    for region_id, loot in p6["loot_changes"].items():
        working["regions"][region_id]["loot"] = loot

    # phase 7: economic yield on post-combat ownership
    p7 = resolve_yield(working, batches, config, seed)
    for force_id, change in p7["essence_changes"].items():
        working["forces"][force_id]["essence"] += change
    for region_id, loot in p7["loot_changes"].items():
        working["regions"][region_id]["loot"] = loot

    # phase 8: quest objectives against post-combat state
    p8 = resolve_quests(working, batches, config, seed)
    for actor, change in p8["essence_changes"].items():
        pool = working["adventurers"] if actor.startswith("adventurer-") else working["forces"]
        pool[actor]["essence"] += change
    for adventurer_id, by_force in p8["reputation_changes"].items():
        for force_id, change in by_force.items():
            working["adventurers"][adventurer_id]["reputation"][force_id] += change
    for quest_id, progress in p8["quest_progress"].items():
        working["quests"]["active"][quest_id]["progress"] = progress
    for quest_id, claimants in p8["quest_claims"].items():
        working["quests"]["active"][quest_id]["claimed_by"] = claimants
    for quest_id, status in p8["quests_resolved"].items():
        quest = working["quests"]["active"].pop(quest_id)
        quest["status"] = status
        quest["resolved_tick"] = tick
        working["quests"]["resolved"][quest_id] = quest
    for death in p8["adventurer_deaths"]:
        del working["adventurers"][death["id"]]
    working["graveyard"].extend(copy.deepcopy(p8["graveyard_additions"]))

    # phase 9: quest spawning by triggers
    deaths_this_tick = p5["adventurer_deaths"] + p8["adventurer_deaths"]
    working["adventurer_deaths_this_tick"] = deaths_this_tick
    p9 = resolve_quest_spawn(working, batches, config, seed)
    del working["adventurer_deaths_this_tick"]
    working["quests"]["active"].update(copy.deepcopy(p9["quests_spawned"]))

    # phase 10: supremacy counter / coronation
    p10 = resolve_supremacy(working, batches, config, seed)
    working["supremacy"] = copy.deepcopy(p10["supremacy"])

    # phase 11: chronicle (lore lives outside the engine, write-only)
    rejected = sorted(
        p2["rejected_orders"] + p3["rejected_orders"] + p4["rejected_orders"]
        + p6["rejected_orders"] + p8["rejected_orders"],
        key=lambda r: (r["actor"], r["index"]),
    )
    working["tick_events"] = {
        "batches": batches,
        "substitutions": p1["substitutions"],
        "rejected_orders": rejected,
        "pending_combats": p4["pending_combats"],
        "combats": p5["combats"],
        "yields": p7["essence_changes"],
        "quests_spawned": p9["quests_spawned"],
        "quests_resolved": p8["quests_resolved"],
        "adventurer_moves": p4["adventurer_moves"],
        "loot_claims": p6["essence_changes"],
        "adventurer_spawned": sorted(p2["spawned"]),
        "adventurer_deaths": deaths_this_tick,
        "supremacy": p10,
    }
    p11 = resolve_chronicle(working, batches, config, seed)
    del working["tick_events"]

    # assembly: tick pointer, combat memory, cached totals — then the cage
    working["tick"] = tick
    working["combats_last_tick"] = p5["combat_regions"]
    for force_id in working["forces"]:
        working["forces"][force_id]["units"] = sum(
            r["units"] for r in working["regions"].values() if r["owner"] == force_id
        )
    validate_world(working)

    write_state(state_dir, working, p11["chronicle"])
    return working
