from pathlib import Path

import pytest
import yaml

from engine.config import ConfigError, load_era_config

ERA_YML = Path(__file__).resolve().parent.parent / "world" / "era.yml"


def _mutated_copy(tmp_path, mutate):
    data = yaml.safe_load(ERA_YML.read_text(encoding="utf-8"))
    mutate(data)
    copy = tmp_path / "era.yml"
    copy.write_text(yaml.safe_dump(data), encoding="utf-8")
    return copy


def test_shipped_era_yml_loads():
    cfg = load_era_config(ERA_YML)
    assert cfg.era.seed == 20260706
    assert cfg.coronation.supremacy_threshold == 0.45
    assert cfg.economy.recruit_cost == 2
    assert cfg.combat.tie_favors == "defender"
    assert cfg.adventurer.personal_quest.type == "survive"
    assert cfg.quests.rewards.dethrone == 15
    assert cfg.map.arms == 3


def test_fortify_cost_curve_escalates_by_level():
    cfg = load_era_config(ERA_YML)
    # cost to advance FROM level 0/1/2 (0-indexed) - strictly widening, not flat
    assert cfg.economy.fortify_cost.at_level(0) == 5
    assert cfg.economy.fortify_cost.at_level(1) == 10
    assert cfg.economy.fortify_cost.at_level(2) == 20


def test_fortify_bonus_is_cumulative_per_level_not_a_flat_multiplier():
    cfg = load_era_config(ERA_YML)
    assert cfg.economy.fortify_bonus.at_level(0) == 0  # unfortified
    assert cfg.economy.fortify_bonus.at_level(1) == 2
    assert cfg.economy.fortify_bonus.at_level(2) == 5
    assert cfg.economy.fortify_bonus.at_level(3) == 10


def test_decree_surge_surcharge_escalates_and_caps_at_the_third_tier():
    cfg = load_era_config(ERA_YML)
    assert cfg.economy.decree_surge_surcharge.at_streak(1) == 5
    assert cfg.economy.decree_surge_surcharge.at_streak(2) == 10
    assert cfg.economy.decree_surge_surcharge.at_streak(3) == 20
    assert cfg.economy.decree_surge_surcharge.at_streak(4) == 20  # never doubles past tier 3


def test_trade_success_pct_by_depth_tier():
    cfg = load_era_config(ERA_YML)
    assert cfg.adventurer.trade_cost == 3
    assert cfg.adventurer.trade_success_pct.for_tier("ring") == 50
    assert cfg.adventurer.trade_success_pct.for_tier("arm") == 75
    assert cfg.adventurer.trade_success_pct.for_tier("capital") == 100


def test_guild_bronze_config():
    cfg = load_era_config(ERA_YML)
    assert cfg.guild.bronze.travel_deadline == 3
    assert cfg.guild.bronze.hold_n_ticks == 2
    assert cfg.guild.bronze.essence_hit == 1
    assert cfg.guild.bronze.essence_miss == 2
    assert cfg.guild.bronze.reputation_hit == 1
    assert cfg.guild.bronze.essence_miss > cfg.guild.bronze.essence_hit  # never a worse outcome


def test_fortify_upkeep_escalates_by_level():
    cfg = load_era_config(ERA_YML)
    assert cfg.economy.fortify_upkeep.at_level(0) == 0  # unfortified
    assert cfg.economy.fortify_upkeep.at_level(1) == 1
    assert cfg.economy.fortify_upkeep.at_level(2) == 3
    assert cfg.economy.fortify_upkeep.at_level(3) == 6


def test_missing_key_fails_naming_the_key(tmp_path):
    copy = _mutated_copy(tmp_path, lambda d: d["economy"].pop("recruit_cost"))
    with pytest.raises(ConfigError, match=r"economy: missing key\(s\): recruit_cost"):
        load_era_config(copy)


def test_missing_nested_key_fails_naming_the_key(tmp_path):
    copy = _mutated_copy(
        tmp_path, lambda d: d["reputation"]["deltas"].pop("trade_per_tick")
    )
    with pytest.raises(ConfigError, match=r"reputation\.deltas.*trade_per_tick"):
        load_era_config(copy)


def test_extra_key_fails_naming_the_key(tmp_path):
    def add_key(d):
        d["economy"]["mana_cost"] = 7

    copy = _mutated_copy(tmp_path, add_key)
    with pytest.raises(ConfigError, match=r"economy: unknown key\(s\): mana_cost"):
        load_era_config(copy)


def test_wrong_type_fails_naming_the_key(tmp_path):
    def break_type(d):
        d["era"]["seed"] = "not-a-number"

    copy = _mutated_copy(tmp_path, break_type)
    with pytest.raises(ConfigError, match=r"era\.seed"):
        load_era_config(copy)
