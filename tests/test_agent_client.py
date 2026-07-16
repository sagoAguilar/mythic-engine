import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from agent_client.client import ClientError, generate_move, write_move
from agent_client.context import build_context
from agent_client.llm import LLMConfig
from engine.config import load_era_config
from engine.validate import validate_move

REPO_ROOT = Path(__file__).resolve().parent.parent


def _repo_copy(tmp_path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    for sub in ("world", "moves", "personas"):
        shutil.copytree(REPO_ROOT / sub, root / sub)
    return root


class _ToolUseBlock:
    def __init__(self, name, input_):
        self.type = "tool_use"
        self.name = name
        self.input = input_


class _FakeAnthropic:
    """Records every call and returns the next programmed response."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        orders = self._responses.pop(0)
        return SimpleNamespace(content=[_ToolUseBlock("propose_orders", {"orders": orders})])


def test_build_context_targets_next_tick_and_includes_history(tmp_path):
    root = _repo_copy(tmp_path)
    ctx = build_context(root, "force-1")

    world_tick = int((root / "world" / "tick.txt").read_text().strip())
    assert ctx["tick"] == world_tick + 1
    assert ctx["force_id"] == "force-1"
    actors_seen = {batch["actor"] for batch in ctx["history"]}
    assert actors_seen == {"force-1", "force-2", "force-3"}


def test_build_context_unknown_force_raises(tmp_path):
    root = _repo_copy(tmp_path)
    with pytest.raises(KeyError):
        build_context(root, "force-9")


def test_generate_move_returns_valid_batch_on_first_try(tmp_path):
    root = _repo_copy(tmp_path)
    config = load_era_config(root / "world" / "era.yml")
    fake = _FakeAnthropic([[{"action": "recruit", "region": "capital-1", "count": 1}]])

    batch = generate_move(root, "force-1", llm_client=fake, llm_config=LLMConfig())

    assert batch["actor"] == "force-1"
    assert batch["origin"] == "agent"
    assert batch["tick"] == int((root / "world" / "tick.txt").read_text().strip()) + 1
    validate_move(batch, config)  # does not raise
    assert len(fake.calls) == 1


def test_generate_move_retries_after_rejection_then_succeeds(tmp_path):
    root = _repo_copy(tmp_path)
    config = load_era_config(root / "world" / "era.yml")
    over_cap = [{"action": "recruit", "region": "capital-1", "count": 1}] * (config.orders.cap_force + 1)
    valid = [{"action": "recruit", "region": "capital-1", "count": 1}]
    fake = _FakeAnthropic([over_cap, valid])

    batch = generate_move(root, "force-1", llm_client=fake, llm_config=LLMConfig(), max_attempts=3)

    assert batch["orders"] == valid
    assert len(fake.calls) == 2
    # the retry must surface the previous rejection back to the model
    assert "rejected" in fake.calls[1]["messages"][0]["content"]


def test_generate_move_gives_up_after_max_attempts(tmp_path):
    root = _repo_copy(tmp_path)
    bad = [{"action": "gather", "region": "capital-1", "count": 1}]  # removed from catalog
    fake = _FakeAnthropic([bad, bad])

    with pytest.raises(ClientError):
        generate_move(root, "force-1", llm_client=fake, llm_config=LLMConfig(), max_attempts=2)

    assert len(fake.calls) == 2


def test_write_move_round_trips_through_validate(tmp_path):
    root = _repo_copy(tmp_path)
    config = load_era_config(root / "world" / "era.yml")
    batch = {
        "actor": "force-1",
        "tick": 2,
        "origin": "agent",
        "orders": [{"action": "recruit", "region": "capital-1", "count": 1}],
    }

    path = write_move(root, batch)

    assert path == root / "moves" / "tick-2" / "force-1.yml"
    reloaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert reloaded == batch
    validate_move(reloaded, config)  # does not raise
