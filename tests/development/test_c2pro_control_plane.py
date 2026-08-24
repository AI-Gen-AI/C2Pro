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
    assert all(item["work_id"] != "C2PRO-DEV-01" for item in queue["items"])


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
    assert "model" not in work
    assert "provider" not in work


def test_same_work_can_move_between_principals_without_identity_change() -> None:
    current = validator.load_yaml(ROOT / ".c2pro" / "control" / "current.yaml")
    queue = validator.load_yaml(ROOT / ".c2pro" / "control" / "work-queue.yaml")
    active_id = current["active_work"][0]
    item = next(item for item in queue["items"] if item["work_id"] == active_id)
    work = validator.load_yaml(ROOT / item["work_ref"])
    initial_identity = validator.stable_work_identity(work)

    claude_assignment = copy.deepcopy(work)
    claude_assignment["worker_selection"]["selected"] = "claude_code"
    codex_assignment = copy.deepcopy(work)
    codex_assignment["worker_selection"]["selected"] = "codex"

    assert validator.stable_work_identity(claude_assignment) == initial_identity
    assert validator.stable_work_identity(codex_assignment) == initial_identity
    assert claude_assignment["worker_selection"]["selected"] != codex_assignment["worker_selection"]["selected"]


def test_canonical_roles_are_model_and_worker_neutral() -> None:
    profiles = validator.validate_role_profiles()
    assert set(profiles) == validator.CANONICAL_ROLES
    for profile in profiles.values():
        assert not (validator.mapping_keys(profile) & validator.ROLE_FORBIDDEN_KEYS)


def test_only_claude_and_codex_are_principal_gate_eligible() -> None:
    profiles = validator.validate_role_profiles()
    routing = validator.validate_routing(profiles)
    workers = routing["workers"]
    principal_gate_eligible = {worker_id for worker_id, config in workers.items() if config["principal_gate_eligible"]}
    assert principal_gate_eligible == {"claude_code", "codex"}
    for worker_id in validator.SUBORDINATE_WORKERS:
        assert workers[worker_id]["class"] == "subordinate"
        assert workers[worker_id]["principal_gate_eligible"] is False


def test_material_self_approval_is_forbidden() -> None:
    profiles = validator.validate_role_profiles()
    routing = validator.validate_routing(profiles)
    review_policy = validator.validate_review_policy()
    assert routing["principal_gate"]["material_reviewer_must_differ_from_implementation_worker"] is True
    assert routing["principal_gate"]["same_worker_dual_role_does_not_satisfy_independence"] is True
    assert review_policy["principal_independence"]["material_or_higher_same_worker_review_forbidden"] is True


def test_high_risk_work_requires_principal_challenger_and_synthesis() -> None:
    policy = validator.validate_review_policy()
    for risk in ("architecture", "security", "high_blast_radius"):
        config = policy["risk_classes"][risk]
        assert config["independent_principal_review"] == "required"
        assert config["challenger"] == "required"
        assert config["orchestrator_synthesis"] is True


def test_open_ended_model_debate_is_not_default() -> None:
    policy = validator.validate_review_policy()
    assert policy["challenger_policy"]["open_ended_debate_default"] is False
    assert policy["challenger_policy"]["directed_adjudication_round_max"] == 1


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


def test_routing_validator_rejects_subordinate_principal_promotion(monkeypatch: pytest.MonkeyPatch) -> None:
    profiles = validator.validate_role_profiles()
    routing = validator.load_yaml(ROOT / ".c2pro" / "control" / "routing.yaml")
    invalid = copy.deepcopy(routing)
    invalid["workers"]["gemini_cli"]["principal_gate_eligible"] = True
    real_load = validator.load_yaml

    def fake_load(path: Path):
        if path == validator.CONTROL / "routing.yaml":
            return invalid
        return real_load(path)

    monkeypatch.setattr(validator, "load_yaml", fake_load)
    with pytest.raises(ValueError, match="cannot satisfy principal gate"):
        validator.validate_routing(profiles)


def test_review_policy_rejects_unbounded_debate(monkeypatch: pytest.MonkeyPatch) -> None:
    policy = validator.load_yaml(ROOT / ".c2pro" / "control" / "review-policy.yaml")
    invalid = copy.deepcopy(policy)
    invalid["challenger_policy"]["open_ended_debate_default"] = True
    real_load = validator.load_yaml

    def fake_load(path: Path):
        if path == validator.CONTROL / "review-policy.yaml":
            return invalid
        return real_load(path)

    monkeypatch.setattr(validator, "load_yaml", fake_load)
    with pytest.raises(ValueError, match="open-ended debate must remain disabled"):
        validator.validate_review_policy()


def test_legacy_sources_are_noncanonical_and_not_deleted_early() -> None:
    policy = validator.load_yaml(ROOT / ".c2pro" / "control" / "legacy-compatibility.yaml")
    assert policy["canonical_write_target"] == ".c2pro"
    for source in policy["legacy_sources"].values():
        assert source["canonical"] is False
        assert source["delete_before_reconciliation"] is False


def test_schema_artifacts_are_closed_draft_2020_12_objects() -> None:
    validator.validate_schema_artifacts()
