"""TDD unit tests for G2 legacy machine-derived closure (pre-schema work items).

C2PRO-DEV-02 (PR #564) merged 2026-08-24, before the c2pro-implementation-result-v1
schema existed (introduced with G1, PR #597, merged 2026-09-06). No worker ever
produced, or could have produced, a conforming structured result for it.
`core.legacy_closure.reconcile_legacy_closure` closes such work using ONLY
machine-verifiable Git/GitHub evidence, on a code path that is structurally
distinct from `core.reconciler.reconcile_result` so it can never be mistaken
for a genuine worker self-report.
"""
from __future__ import annotations

import copy

import pytest
import yaml

from core.legacy_closure import (
    LegacyClosureError,
    LegacyClosureValidationError,
    reconcile_legacy_closure,
)


@pytest.fixture
def mock_control_plane(tmp_path):
    """Provisions a mocked .c2pro control directory with DEV-02 as open work."""
    control_dir = tmp_path / ".c2pro" / "control"
    control_dir.mkdir(parents=True, exist_ok=True)

    wq_data = {
        "schema": "c2pro-work-queue-v1",
        "schema_version": 1,
        "queue_policy": {
            "open_only": True,
            "completed_items_forbidden": True,
            "historical_source": "git_pr_ci_evidence",
        },
        "items": [
            {
                "work_id": "C2PRO-DEV-02",
                "status": "in_progress",
                "role": "orchestrator",
                "work_ref": ".c2pro/work/C2PRO-DEV-02.yaml",
                "priority": "P0",
                "depends_on": ["C2PRO-DEV-01"],
                "review_policy": "principal_and_challenger",
            },
            {
                "work_id": "C2PRO-DEV-03",
                "status": "ready",
                "role": "orchestrator",
                "work_ref": None,
                "priority": "P0",
                "depends_on": ["C2PRO-DEV-00"],
                "review_policy": "independent_principal",
            },
        ],
    }
    with open(control_dir / "work-queue.yaml", "w", encoding="utf-8") as f:
        yaml.dump(wq_data, f)

    current_data = {
        "schema": "c2pro-current-v1",
        "schema_version": 1,
        "repository": "AI-Gen-AI/C2Pro",
        "control_status": "transition",
        "baseline": {"main_sha": "3fa846d60cecd14239ddb0a953be5e34bede463d"},
        "active_work": ["C2PRO-DEV-02"],
        "next_eligible_work": "C2PRO-DEV-03",
    }
    with open(control_dir / "current.yaml", "w", encoding="utf-8") as f:
        yaml.dump(current_data, f)

    return control_dir


@pytest.fixture
def valid_dev02_evidence():
    """Real, machine-verified Git/GitHub facts for C2PRO-DEV-02 (PR #564)."""
    return {
        "work_id": "C2PRO-DEV-02",
        "branch": "feat/c2pro-dev-02-role-authority-v1",
        "base_sha": "3fa846d60cecd14239ddb0a953be5e34bede463d",
        "head_sha": "f633d5ea22fd4f464b290fe36bc4891563efa1ef",
        "merge_commit_sha": "0400c05e8af1458aaa14bc47a8378d9cdd560284",
        "authoritative_main_sha": "32eba9431ddaab198088a09fe9294ae5ecc38318",
        "main_contains_merge_commit": True,
        "pr_url": "https://github.com/AI-Gen-AI/C2Pro/pull/564",
        "pr_state": "merged",
        "ci_status": "success",
        "provenance": {
            "derived_from": ["git_merge_base", "github_pull_request_api", "github_commit_status_api"],
            "reason": (
                "PR #564 merged 2026-08-24, predating the c2pro-implementation-result-v1 "
                "schema introduced with G1 (PR #597, merged 2026-09-06). No worker result "
                "block exists or was fabricated for this closure."
            ),
        },
    }


def test_red_rejects_worker_result_schema_declaration(mock_control_plane, valid_dev02_evidence):
    """Evidence that declares itself as a worker result must be refused outright."""
    evidence = copy.deepcopy(valid_dev02_evidence)
    evidence["schema"] = "c2pro-implementation-result-v1"

    with pytest.raises(LegacyClosureValidationError, match="MUST NOT declare schema"):
        reconcile_legacy_closure(evidence, control_dir=mock_control_plane)


@pytest.mark.parametrize(
    "missing_field",
    [
        "work_id",
        "branch",
        "base_sha",
        "head_sha",
        "merge_commit_sha",
        "authoritative_main_sha",
        "pr_url",
        "pr_state",
        "ci_status",
        "provenance",
    ],
)
def test_red_missing_required_field(mock_control_plane, valid_dev02_evidence, missing_field):
    evidence = copy.deepcopy(valid_dev02_evidence)
    del evidence[missing_field]

    with pytest.raises(LegacyClosureValidationError, match="Missing required legacy evidence fields"):
        reconcile_legacy_closure(evidence, control_dir=mock_control_plane)


def test_red_invalid_sha_format(mock_control_plane, valid_dev02_evidence):
    evidence = copy.deepcopy(valid_dev02_evidence)
    evidence["head_sha"] = "not-a-sha"

    with pytest.raises(LegacyClosureValidationError, match="Invalid head_sha"):
        reconcile_legacy_closure(evidence, control_dir=mock_control_plane)


def test_red_pr_state_not_merged(mock_control_plane, valid_dev02_evidence):
    evidence = copy.deepcopy(valid_dev02_evidence)
    evidence["pr_state"] = "open"

    with pytest.raises(LegacyClosureValidationError, match="pr_state == 'merged'"):
        reconcile_legacy_closure(evidence, control_dir=mock_control_plane)


def test_red_main_does_not_contain_merge_commit(mock_control_plane, valid_dev02_evidence):
    evidence = copy.deepcopy(valid_dev02_evidence)
    evidence["main_contains_merge_commit"] = False

    with pytest.raises(LegacyClosureValidationError, match="main_contains_merge_commit must be verified True"):
        reconcile_legacy_closure(evidence, control_dir=mock_control_plane)


def test_red_provenance_missing_reason(mock_control_plane, valid_dev02_evidence):
    evidence = copy.deepcopy(valid_dev02_evidence)
    evidence["provenance"] = {"derived_from": ["git"]}

    with pytest.raises(LegacyClosureValidationError, match="provenance.reason"):
        reconcile_legacy_closure(evidence, control_dir=mock_control_plane)


def test_red_unknown_work_id_not_in_queue(mock_control_plane, valid_dev02_evidence):
    evidence = copy.deepcopy(valid_dev02_evidence)
    evidence["work_id"] = "C2PRO-DEV-99"

    with pytest.raises(LegacyClosureValidationError, match="not registered in the active work queue"):
        reconcile_legacy_closure(evidence, control_dir=mock_control_plane)


def test_red_blocked_by_incomplete_transaction(mock_control_plane, valid_dev02_evidence):
    tx_path = mock_control_plane / "reconciliation-transaction.yaml"
    with open(tx_path, "w", encoding="utf-8") as f:
        yaml.dump({"schema": "c2pro-reconciliation-transaction-v1", "state": "prepared", "work_id": "C2PRO-DEV-02"}, f)

    with pytest.raises(LegacyClosureError, match="Incomplete transaction detected"):
        reconcile_legacy_closure(valid_dev02_evidence, control_dir=mock_control_plane)


def test_green_happy_path_closes_work_and_mutates_canonical_state(mock_control_plane, valid_dev02_evidence):
    result = reconcile_legacy_closure(valid_dev02_evidence, control_dir=mock_control_plane)

    assert result["status"] == "LEGACY_CLOSED"
    assert result["work_id"] == "C2PRO-DEV-02"
    assert result["idempotent"] is False

    with open(mock_control_plane / "work-queue.yaml", encoding="utf-8") as f:
        wq = yaml.safe_load(f)
    remaining_ids = [item["work_id"] for item in wq["items"]]
    assert "C2PRO-DEV-02" not in remaining_ids
    assert "C2PRO-DEV-03" in remaining_ids  # untouched, unrelated work preserved

    with open(mock_control_plane / "current.yaml", encoding="utf-8") as f:
        current = yaml.safe_load(f)
    assert current["baseline"]["main_sha"] == "32eba9431ddaab198088a09fe9294ae5ecc38318"
    assert "C2PRO-DEV-02" not in current["active_work"]

    with open(mock_control_plane / "reconciliation-history.yaml", encoding="utf-8") as f:
        history = yaml.safe_load(f)
    entry = history["completed_work"]["C2PRO-DEV-02"]
    assert entry["closure_type"] == "legacy_machine_derived"
    assert entry["head_sha"] == "f633d5ea22fd4f464b290fe36bc4891563efa1ef"
    assert entry["merge_commit_sha"] == "0400c05e8af1458aaa14bc47a8378d9cdd560284"
    assert entry["main_sha_after_merge"] == "32eba9431ddaab198088a09fe9294ae5ecc38318"
    assert "provenance" in entry
    assert "reconciled_at" in entry

    # No transaction marker left behind after a successful commit
    assert not (mock_control_plane / "reconciliation-transaction.yaml").exists()
    assert not (mock_control_plane / "work-queue.yaml.tmp").exists()


def test_idempotent_replay_makes_no_additional_mutation(mock_control_plane, valid_dev02_evidence):
    first = reconcile_legacy_closure(valid_dev02_evidence, control_dir=mock_control_plane)
    assert first["idempotent"] is False

    wq_before = (mock_control_plane / "work-queue.yaml").read_text(encoding="utf-8")
    history_before = (mock_control_plane / "reconciliation-history.yaml").read_text(encoding="utf-8")

    second = reconcile_legacy_closure(valid_dev02_evidence, control_dir=mock_control_plane)
    assert second["status"] == "success"
    assert second["idempotent"] is True

    assert (mock_control_plane / "work-queue.yaml").read_text(encoding="utf-8") == wq_before
    assert (mock_control_plane / "reconciliation-history.yaml").read_text(encoding="utf-8") == history_before


def test_conflicting_replay_is_rejected(mock_control_plane, valid_dev02_evidence):
    reconcile_legacy_closure(valid_dev02_evidence, control_dir=mock_control_plane)

    conflicting = copy.deepcopy(valid_dev02_evidence)
    conflicting["merge_commit_sha"] = "1234567890abcdef1234567890abcdef12345678"[:40]
    assert len(conflicting["merge_commit_sha"]) == 40

    # C2PRO-DEV-02 is already removed from the queue by the first call, so a
    # conflicting replay must be rejected because it is already closed with
    # different evidence -- never silently re-applied.
    with pytest.raises(LegacyClosureValidationError, match="already closed with conflicting evidence"):
        reconcile_legacy_closure(conflicting, control_dir=mock_control_plane)
