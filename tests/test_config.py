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
