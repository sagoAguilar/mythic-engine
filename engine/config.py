"""Typed loader for ``world/era.yml``.

All tunable game values live in era.yml (see docs/intent.md); the engine
never hardcodes them. This module parses that file into a frozen dataclass
tree and rejects any mismatch between file and schema: a missing key, an
unknown key, or a wrong value type raises :class:`ConfigError` naming the
offending key by its dotted path.
"""

import dataclasses
from dataclasses import dataclass
from pathlib import Path

import yaml


class ConfigError(Exception):
    """The era.yml file does not match the expected schema."""


@dataclass(frozen=True)
class Era:
    number: int
    seed: int
    tick_cap: int
    cadence: str


@dataclass(frozen=True)
class Coronation:
    supremacy_threshold: float
    k_ticks: int


@dataclass(frozen=True)
class Orders:
    cap_force: int
    cap_adventurer: int
    npc_cap: int


@dataclass(frozen=True)
class Economy:
    yield_neutral: int
    yield_capital: int
    yield_ring: int
    recruit_cost: int
    fortify_cost: int
    fortify_bonus: int
    fortify_cap: int


@dataclass(frozen=True)
class Combat:
    tie_favors: str


@dataclass(frozen=True)
class PersonalQuest:
    type: str
    target: str


@dataclass(frozen=True)
class Adventurer:
    baseline_essence: int
    trade_cap_per_tick: int
    loot_burn_fraction: float
    loot_dissipation_ticks: int
    kill_order_cost: int
    personal_quest: PersonalQuest


@dataclass(frozen=True)
class ReputationDeltas:
    trade_per_tick: int
    quest_damages_force: int
    quest_damages_force_rivals: int
    refuge_per_tick: int


@dataclass(frozen=True)
class ReputationThresholds:
    trade: int
    refuge: int
    errands_v2: int


@dataclass(frozen=True)
class Reputation:
    scale_min: int
    scale_max: int
    initial: int
    decay_intra_era: int
    cataclysm_multiplier: float
    deltas: ReputationDeltas
    thresholds: ReputationThresholds


@dataclass(frozen=True)
class QuestRewards:
    raid: int
    blockade: int
    attrition: int
    dethrone: int


@dataclass(frozen=True)
class QuestTriggers:
    supremacy_minor: float
    supremacy_major: float
    adventurer_death_vengeance: str


@dataclass(frozen=True)
class Quests:
    max_active_major: int
    max_active_minor: int
    window_ticks: int
    blockade_n_ticks: int
    attrition_delta: int
    rewards: QuestRewards
    triggers: QuestTriggers


@dataclass(frozen=True)
class Map:
    arms: int
    regions_per_arm: int
    ring_size: int


@dataclass(frozen=True)
class Budget:
    tokens_per_era: int


@dataclass(frozen=True)
class EraConfig:
    era: Era
    coronation: Coronation
    orders: Orders
    economy: Economy
    combat: Combat
    adventurer: Adventurer
    reputation: Reputation
    quests: Quests
    map: Map
    budget: Budget


def _build(cls: type, data: object, path: str):
    label = path or "<root>"
    if not isinstance(data, dict):
        raise ConfigError(f"{label}: expected a mapping, got {type(data).__name__}")

    fields = {f.name: f for f in dataclasses.fields(cls)}
    missing = sorted(fields.keys() - data.keys())
    if missing:
        raise ConfigError(f"{label}: missing key(s): {', '.join(missing)}")
    extra = sorted(data.keys() - fields.keys())
    if extra:
        raise ConfigError(f"{label}: unknown key(s): {', '.join(extra)}")

    kwargs = {}
    for name, field in fields.items():
        value = data[name]
        child = f"{path}.{name}" if path else name
        if dataclasses.is_dataclass(field.type):
            kwargs[name] = _build(field.type, value, child)
        elif field.type is float:
            # YAML writes whole-number floats as ints; bool is not a number here.
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ConfigError(
                    f"{child}: expected a number, got {type(value).__name__}"
                )
            kwargs[name] = float(value)
        elif field.type is int:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ConfigError(
                    f"{child}: expected an integer, got {type(value).__name__}"
                )
            kwargs[name] = value
        elif field.type is str:
            if not isinstance(value, str):
                raise ConfigError(
                    f"{child}: expected a string, got {type(value).__name__}"
                )
            kwargs[name] = value
        else:  # pragma: no cover - would be a bug in this schema, not in era.yml
            raise ConfigError(f"{child}: unsupported schema type {field.type!r}")
    return cls(**kwargs)


def load_era_config(path: str | Path) -> EraConfig:
    """Parse *path* (an era.yml file) into an :class:`EraConfig`.

    Raises :class:`ConfigError` if the file is missing, is not a YAML
    mapping, or deviates from the schema in any key or value type.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path} is not valid YAML: {exc}") from exc
    return _build(EraConfig, data, "")
