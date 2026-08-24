from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = ROOT / "scripts" / "development" / "validate_c2pro_control.py"
SPEC = importlib.util.spec_from_file_location("validate_c2pro_control", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def test_canonical_control_plane_validates_and_meets_hot_budget() -> None:
    total = validator.validate()
    current = validator.load_yaml(ROOT / ".c2pro" / "control" / "current.yaml")
    assert total <= current["context_budget"]["bootstrap_hot_max_bytes"]
    assert total <= 16 * 1024


def test_work_queue_contains_only_open_work() -> None:
    queue = validator.load_yaml(ROOT / ".c2pro" / "control" / "work-queue.yaml")
    assert queue["items"]
    assert {item["status"] for item in queue["items"]} <= validator.OPEN_STATES
    assert all(item["status"] != "completed" for item in queue["items"])


def test_active_work_identity_is_model_independent() -> None:
    current = validator.load_yaml(ROOT / ".c2pro" / "control" / "current.yaml")
    queue = validator.load_yaml(ROOT / ".c2pro" / "control" / "work-queue.yaml")
    active_id = current["active_work"][0]
    item = next(item for item in queue["items"] if item["work_id"] == active_id)
    work = validator.load_yaml(ROOT / item["work_ref"])
    assert work["work_id"] == active_id
    assert work["base_sha"] == current["baseline"]["main_sha"]
    assert work["worker_selection"]["selected"] is None
    assert work["role"] == item["role"]


def test_queue_validator_rejects_completed_history(monkeypatch: pytest.MonkeyPatch) -> None:
    current = validator.load_yaml(ROOT / ".c2pro" / "control" / "current.yaml")
    queue = validator.load_yaml(ROOT / ".c2pro" / "control" / "work-queue.yaml")
    invalid = copy.deepcopy(queue)
    invalid["items"][0]["status"] = "completed"
    real_load = validator.load_yaml

    def fake_load(path: Path):
        if path == validator.CONTROL / "work-queue.yaml":
            return invalid
        return real_load(path)

    monkeypatch.setattr(validator, "load_yaml", fake_load)
    with pytest.raises(ValueError, match="historical/completed status forbidden"):
        validator.validate_queue(current)


def test_current_validator_rejects_completed_history_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    current = validator.load_yaml(ROOT / ".c2pro" / "control" / "current.yaml")
    invalid = copy.deepcopy(current)
    invalid["history"]["completed_work_in_hot_state"] = True
    real_load = validator.load_yaml

    def fake_load(path: Path):
        if path == validator.CONTROL / "current.yaml":
            return invalid
        return real_load(path)

    monkeypatch.setattr(validator, "load_yaml", fake_load)
    with pytest.raises(ValueError, match="completed history is forbidden"):
        validator.validate_current()


def test_legacy_sources_are_noncanonical_and_not_deleted_early() -> None:
    policy = validator.load_yaml(ROOT / ".c2pro" / "control" / "legacy-compatibility.yaml")
    assert policy["canonical_write_target"] == ".c2pro"
    for source in policy["legacy_sources"].values():
        assert source["canonical"] is False
        assert source["delete_before_reconciliation"] is False


def test_schema_artifacts_are_closed_draft_2020_12_objects() -> None:
    validator.validate_schema_artifacts()
