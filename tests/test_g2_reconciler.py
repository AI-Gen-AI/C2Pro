"""TDD unit tests for G2 Canonical Control-Plane Reconciler with full merge evidence gates."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from core.reconciler import ValidationError, reconcile_result


@pytest.fixture
def mock_control_plane(tmp_path):
    """Fixture to provision a complete mocked .c2pro control directory."""
    control_dir = tmp_path / ".c2pro" / "control"
    control_dir.mkdir(parents=True, exist_ok=True)

    # 1. Setup work-queue.yaml
    wq_file = control_dir / "work-queue.yaml"
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
                "depends_on": [],
                "review_policy": "principal_and_challenger",
            }
        ]
    }
    with open(wq_file, "w", encoding="utf-8") as f:
        yaml.dump(wq_data, f)

    # 2. Setup current.yaml
    current_file = control_dir / "current.yaml"
    current_data = {
        "schema": "c2pro-current-v1",
        "schema_version": 1,
        "repository": "AI-Gen-AI/C2Pro",
        "control_status": "transition",
        "baseline": {
            "main_sha": "3fa846d60cecd14239ddb0a953be5e34bede463d",
        },
        "active_work": ["C2PRO-DEV-02"],
    }
    with open(current_file, "w", encoding="utf-8") as f:
        yaml.dump(current_data, f)

    return control_dir


@pytest.fixture
def valid_worker_result():
    """Returns a valid fenced YAML worker implementation result block."""
    return """
```yaml
schema: c2pro-implementation-result-v1
work_id: C2PRO-DEV-02
base_sha: 3fa846d60cecd14239ddb0a953be5e34bede463d
head_sha: 7c3a8347a5bea0c28f2e540559bd515f9afd282a
branch: feat/c2pro-dev-02-role-authority-v1
files_changed:
  - core/supervisor.py
tests:
  - name: test_single_writer_control_plane
    status: PASS
ci_status: success
findings:
  - "BASELINE_FINDING: pre-existing lint warning in supervisor"
  - "NEW_FINDING: added strict supervisor boundary"
  - "ordinary finding without prefix"
residual_risks: []
recommendation: approve
pr_url: https://github.com/AI-Gen-AI/C2Pro/pull/597
```
"""


def test_reconciliation_happy_path(mock_control_plane, valid_worker_result):
    """Test successful G2 reconciliation flow with valid evidence, PR merged, reachable merge commit."""
    remote_evidence = {
        "remote_head_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "pr_head_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "branch": "feat/c2pro-dev-02-role-authority-v1",
        "pr_base_branch": "main",
        "pr_state": "merged",
        "merge_commit_sha": "f00baaf00baaf00baaf00baaf00baaf00baaf00b",
        "authoritative_main_sha": "f00baaf00baaf00baaf00baaf00baaf00baaf00b",
        "main_contains_merge_commit": True,
    }
    ci_evidence = {
        "ci_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "ci_status": "success",
    }

    outcome = reconcile_result(
        valid_worker_result,
        remote_evidence=remote_evidence,
        ci_evidence=ci_evidence,
        control_dir=mock_control_plane,
    )

    assert outcome["status"] == "RECONCILED"
    assert outcome["work_id"] == "C2PRO-DEV-02"
    assert outcome["idempotent"] is False

    # Verify Quality Delta Rule: baseline vs new findings distinguished
    assert "pre-existing lint warning in supervisor" in outcome["baseline_findings"]
    assert "added strict supervisor boundary" in outcome["new_findings"]
    assert "ordinary finding without prefix" in outcome["new_findings"]

    # Verify state updates in .c2pro/control/*
    # 1. Removed from active_work in current.yaml and updated baseline to authoritative main SHA
    with open(mock_control_plane / "current.yaml", encoding="utf-8") as f:
        curr = yaml.safe_load(f)
    assert curr["baseline"]["main_sha"] == "f00baaf00baaf00baaf00baaf00baaf00baaf00b"
    assert "C2PRO-DEV-02" not in curr["active_work"]

    # 2. Removed from work-queue.yaml items
    with open(mock_control_plane / "work-queue.yaml", encoding="utf-8") as f:
        wq = yaml.safe_load(f)
    assert not any(item["work_id"] == "C2PRO-DEV-02" for item in wq.get("items", []))

    # 3. Recorded in reconciliation-history.yaml with separate keys
    with open(mock_control_plane / "reconciliation-history.yaml", encoding="utf-8") as f:
        hist = yaml.safe_load(f)
    assert "C2PRO-DEV-02" in hist["completed_work"]
    record = hist["completed_work"]["C2PRO-DEV-02"]
    assert record["worker_head_sha"] == "7c3a8347a5bea0c28f2e540559bd515f9afd282a"
    assert record["merge_commit_sha"] == "f00baaf00baaf00baaf00baaf00baaf00baaf00b"
    assert record["main_sha_after_merge"] == "f00baaf00baaf00baaf00baaf00baaf00baaf00b"


def test_red_a_remote_head_mismatch(mock_control_plane, valid_worker_result):
    """Test RED A: actual remote HEAD mismatch with the result's head_sha fails."""
    remote_evidence = {
        "remote_head_sha": "diff_sha_99999999999999999999999999999999",
        "pr_head_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "branch": "feat/c2pro-dev-02-role-authority-v1",
    }
    ci_evidence = {
        "ci_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "ci_status": "success",
    }

    with pytest.raises(ValidationError, match="Remote HEAD mismatch"):
        reconcile_result(
            valid_worker_result,
            remote_evidence=remote_evidence,
            ci_evidence=ci_evidence,
            control_dir=mock_control_plane,
        )


def test_red_b_pr_head_mismatch(mock_control_plane, valid_worker_result):
    """Test RED B: actual PR HEAD mismatch with the result's head_sha fails."""
    remote_evidence = {
        "remote_head_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "pr_head_sha": "diff_sha_99999999999999999999999999999999",
        "branch": "feat/c2pro-dev-02-role-authority-v1",
    }
    ci_evidence = {
        "ci_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "ci_status": "success",
    }

    with pytest.raises(ValidationError, match="PR HEAD mismatch"):
        reconcile_result(
            valid_worker_result,
            remote_evidence=remote_evidence,
            ci_evidence=ci_evidence,
            control_dir=mock_control_plane,
        )


def test_red_c_stale_ci_sha(mock_control_plane, valid_worker_result):
    """Test RED C: stale CI evidence fails closed."""
    remote_evidence = {
        "remote_head_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "pr_head_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "branch": "feat/c2pro-dev-02-role-authority-v1",
    }
    ci_evidence = {
        "ci_sha": "stale_sha_1111111111111111111111111111111",
        "ci_status": "success",
    }

    with pytest.raises(ValidationError, match="Stale CI SHA"):
        reconcile_result(
            valid_worker_result,
            remote_evidence=remote_evidence,
            ci_evidence=ci_evidence,
            control_dir=mock_control_plane,
        )


def test_red_d_malformed_implementation_result(mock_control_plane):
    """Test RED D: malformed implementation-result missing pr_url or invalid schema fails."""
    malformed_result = """
```yaml
schema: c2pro-implementation-result-v1
work_id: C2PRO-DEV-02
base_sha: 3fa846d60cecd14239ddb0a953be5e34bede463d
head_sha: 7c3a8347a5bea0c28f2e540559bd515f9afd282a
branch: feat/c2pro-dev-02-role-authority-v1
files_changed: []
tests: []
ci_status: success
findings: []
residual_risks: []
recommendation: approve
# pr_url is missing
```
"""
    remote_evidence = {
        "remote_head_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "pr_head_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "branch": "feat/c2pro-dev-02-role-authority-v1",
    }
    ci_evidence = {
        "ci_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "ci_status": "success",
    }

    with pytest.raises(ValidationError, match="Result schema validation failed.*'pr_url' is a required property"):
        reconcile_result(
            malformed_result,
            remote_evidence=remote_evidence,
            ci_evidence=ci_evidence,
            control_dir=mock_control_plane,
        )


def test_red_e_duplicate_reconciliation(mock_control_plane, valid_worker_result):
    """Test RED E: duplicate reconciliation with identical merge evidence returns success idempotently."""
    remote_evidence = {
        "remote_head_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "pr_head_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "branch": "feat/c2pro-dev-02-role-authority-v1",
        "pr_base_branch": "main",
        "pr_state": "merged",
        "merge_commit_sha": "f00baaf00baaf00baaf00baaf00baaf00baaf00b",
        "authoritative_main_sha": "f00baaf00baaf00baaf00baaf00baaf00baaf00b",
        "main_contains_merge_commit": True,
    }
    ci_evidence = {
        "ci_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "ci_status": "success",
    }

    # First reconciliation
    res1 = reconcile_result(
        valid_worker_result,
        remote_evidence=remote_evidence,
        ci_evidence=ci_evidence,
        control_dir=mock_control_plane,
    )
    assert res1["status"] == "RECONCILED"
    assert res1["idempotent"] is False

    # Second identical reconciliation
    res2 = reconcile_result(
        valid_worker_result,
        remote_evidence=remote_evidence,
        ci_evidence=ci_evidence,
        control_dir=mock_control_plane,
    )
    assert res2["status"] == "success"
    assert res2["idempotent"] is True
    assert "already reconciled" in res2["message"]


def test_red_f_modern_result_attempting_legacy_backlog_blackboard_write(tmp_path, valid_worker_result, monkeypatch):
    """Test RED F: modern task execution does NOT perform legacy Markdown or blackboard.json writes."""
    # Track files opened/written in write mode
    written_paths = []
    original_open = open

    def mock_open(file, mode="r", *args, **kwargs):
        path = Path(file)
        if "w" in mode or "a" in mode:
            written_paths.append(path.name)
        return original_open(file, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", mock_open)

    # Mock control plane structure
    control_dir = tmp_path / ".c2pro" / "control"
    control_dir.mkdir(parents=True, exist_ok=True)
    with open(control_dir / "work-queue.yaml", "w") as f:
        yaml.dump({"items": [{"work_id": "C2PRO-DEV-02"}]}, f)

    remote_evidence = {
        "remote_head_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "pr_head_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "branch": "feat/c2pro-dev-02-role-authority-v1",
        "pr_base_branch": "main",
        "pr_state": "merged",
        "merge_commit_sha": "f00baaf00baaf00baaf00baaf00baaf00baaf00b",
        "authoritative_main_sha": "f00baaf00baaf00baaf00baaf00baaf00b",
        "main_contains_merge_commit": True,
    }
    ci_evidence = {
        "ci_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "ci_status": "success",
    }

    reconcile_result(
        valid_worker_result,
        remote_evidence=remote_evidence,
        ci_evidence=ci_evidence,
        control_dir=control_dir,
    )

    # Must NOT have written to blackboard.json, backlogs, or master backlog
    for name in written_paths:
        assert "blackboard" not in name
        assert "backlog" not in name


def test_red_g_unknown_work_id(mock_control_plane):
    """Test RED G: result with unknown work_id fails validation."""
    unknown_result = """
```yaml
schema: c2pro-implementation-result-v1
work_id: C2PRO-DEV-99
base_sha: 3fa846d60cecd14239ddb0a953be5e34bede463d
head_sha: 7c3a8347a5bea0c28f2e540559bd515f9afd282a
branch: feat/c2pro-dev-02-role-authority-v1
files_changed: []
tests: []
ci_status: success
findings: []
residual_risks: []
recommendation: approve
pr_url: https://github.com/AI-Gen-AI/C2Pro/pull/597
```
"""
    remote_evidence = {
        "remote_head_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "pr_head_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "branch": "feat/c2pro-dev-02-role-authority-v1",
        "pr_base_branch": "main",
        "pr_state": "merged",
        "merge_commit_sha": "f00baaf00baaf00baaf00baaf00baaf00baaf00b",
        "authoritative_main_sha": "f00baaf00baaf00baaf00baaf00baaf00baaf00b",
        "main_contains_merge_commit": True,
    }
    ci_evidence = {
        "ci_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "ci_status": "success",
    }

    with pytest.raises(ValidationError, match="Unknown work_id"):
        reconcile_result(
            unknown_result,
            remote_evidence=remote_evidence,
            ci_evidence=ci_evidence,
            control_dir=mock_control_plane,
        )


def test_red_h_closed_work_conflicting_head(mock_control_plane, valid_worker_result):
    """Test RED H: result for already-closed work with conflicting HEAD/merge evidence fails."""
    remote_evidence = {
        "remote_head_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "pr_head_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "branch": "feat/c2pro-dev-02-role-authority-v1",
        "pr_base_branch": "main",
        "pr_state": "merged",
        "merge_commit_sha": "f00baaf00baaf00baaf00baaf00baaf00baaf00b",
        "authoritative_main_sha": "f00baaf00baaf00baaf00baaf00baaf00baaf00b",
        "main_contains_merge_commit": True,
    }
    ci_evidence = {
        "ci_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "ci_status": "success",
    }

    # Successfully reconcile first
    reconcile_result(
        valid_worker_result,
        remote_evidence=remote_evidence,
        ci_evidence=ci_evidence,
        control_dir=mock_control_plane,
    )

    # Now attempt to reconcile with a conflicting head SHA (valid 40-character hex SHA with letters)
    conflicting_result = valid_worker_result.replace(
        "head_sha: 7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "head_sha: 99999999999999999999999999999999999999aa"
    )

    remote_evidence_conflict = {
        "remote_head_sha": "99999999999999999999999999999999999999aa",
        "pr_head_sha": "99999999999999999999999999999999999999aa",
        "branch": "feat/c2pro-dev-02-role-authority-v1",
        "pr_base_branch": "main",
        "pr_state": "merged",
        "merge_commit_sha": "f00baaf00baaf00baaf00baaf00baaf00baaf00b",
        "authoritative_main_sha": "f00baaf00baaf00baaf00baaf00baaf00baaf00b",
        "main_contains_merge_commit": True,
    }
    ci_evidence_conflict = {
        "ci_sha": "99999999999999999999999999999999999999aa",
        "ci_status": "success",
    }

    with pytest.raises(ValidationError, match="already closed with conflicting merge evidence"):
        reconcile_result(
            conflicting_result,
            remote_evidence=remote_evidence_conflict,
            ci_evidence=ci_evidence_conflict,
            control_dir=mock_control_plane,
        )


def test_i_ci_green_pr_still_open(mock_control_plane, valid_worker_result):
    """Test I: CI green + PR still OPEN returns AWAITING_MERGE, zero mutation to control."""
    remote_evidence = {
        "remote_head_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "pr_head_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "branch": "feat/c2pro-dev-02-role-authority-v1",
        "pr_base_branch": "main",
        "pr_state": "open",
        "merge_commit_sha": None,
        "authoritative_main_sha": "3fa846d60cecd14239ddb0a953be5e34bede463d",
        "main_contains_merge_commit": False,
    }
    ci_evidence = {
        "ci_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "ci_status": "success",
    }

    outcome = reconcile_result(
        valid_worker_result,
        remote_evidence=remote_evidence,
        ci_evidence=ci_evidence,
        control_dir=mock_control_plane,
    )

    assert outcome["status"] == "AWAITING_MERGE"
    assert "still OPEN" in outcome["message"]

    # Verify NO mutations to control files:
    # 1. work item is NOT removed from work-queue.yaml
    with open(mock_control_plane / "work-queue.yaml", encoding="utf-8") as f:
        wq = yaml.safe_load(f)
    assert any(item["work_id"] == "C2PRO-DEV-02" for item in wq.get("items", []))

    # 2. current.yaml remains unchanged
    with open(mock_control_plane / "current.yaml", encoding="utf-8") as f:
        curr = yaml.safe_load(f)
    assert curr["baseline"]["main_sha"] == "3fa846d60cecd14239ddb0a953be5e34bede463d"
    assert "C2PRO-DEV-02" in curr["active_work"]

    # 3. No record created in reconciliation-history.yaml
    assert not (mock_control_plane / "reconciliation-history.yaml").exists()


def test_j_pr_closed_but_not_merged(mock_control_plane, valid_worker_result):
    """Test J: PR CLOSED but not merged fails closed."""
    remote_evidence = {
        "remote_head_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "pr_head_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "branch": "feat/c2pro-dev-02-role-authority-v1",
        "pr_base_branch": "main",
        "pr_state": "closed_unmerged",
        "merge_commit_sha": None,
        "authoritative_main_sha": "3fa846d60cecd14239ddb0a953be5e34bede463d",
        "main_contains_merge_commit": False,
    }
    ci_evidence = {
        "ci_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "ci_status": "success",
    }

    with pytest.raises(ValidationError, match="closed without being merged"):
        reconcile_result(
            valid_worker_result,
            remote_evidence=remote_evidence,
            ci_evidence=ci_evidence,
            control_dir=mock_control_plane,
        )


def test_k_pr_merged_to_wrong_base(mock_control_plane, valid_worker_result):
    """Test K: PR merged to non-main base branch fails closed."""
    remote_evidence = {
        "remote_head_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "pr_head_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "branch": "feat/c2pro-dev-02-role-authority-v1",
        "pr_base_branch": "develop",
        "pr_state": "merged",
        "merge_commit_sha": "f00baaf00baaf00baaf00baaf00baaf00baaf00b",
        "authoritative_main_sha": "f00baaf00baaf00baaf00baaf00baaf00baaf00b",
        "main_contains_merge_commit": True,
    }
    ci_evidence = {
        "ci_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "ci_status": "success",
    }

    with pytest.raises(ValidationError, match="base branch must be 'main'"):
        reconcile_result(
            valid_worker_result,
            remote_evidence=remote_evidence,
            ci_evidence=ci_evidence,
            control_dir=mock_control_plane,
        )


def test_l_squash_merge(mock_control_plane, valid_worker_result):
    """Test L: squash merge is fully accepted, setting baseline.main_sha to verified main, never worker head."""
    remote_evidence = {
        "remote_head_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "pr_head_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "branch": "feat/c2pro-dev-02-role-authority-v1",
        "pr_base_branch": "main",
        "pr_state": "merged",
        "merge_commit_sha": "squash_merge_commit_sha_55555555555555",
        "authoritative_main_sha": "verified_main_head_sha_999999999999999",
        "main_contains_merge_commit": True,
    }
    ci_evidence = {
        "ci_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "ci_status": "success",
    }

    # worker_head_sha (7c3a8347a5bea0c28f2e540559bd515f9afd282a) != merge_commit_sha (squash_merge_commit_sha_55555555555555)
    outcome = reconcile_result(
        valid_worker_result,
        remote_evidence=remote_evidence,
        ci_evidence=ci_evidence,
        control_dir=mock_control_plane,
    )

    assert outcome["status"] == "RECONCILED"

    with open(mock_control_plane / "current.yaml", encoding="utf-8") as f:
        curr = yaml.safe_load(f)
    assert curr["baseline"]["main_sha"] == "verified_main_head_sha_999999999999999"
    assert curr["baseline"]["main_sha"] != "7c3a8347a5bea0c28f2e540559bd515f9afd282a"


def test_m_reported_merge_commit_not_reachable(mock_control_plane, valid_worker_result):
    """Test M: reported merge commit not reachable from main fails closed."""
    remote_evidence = {
        "remote_head_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "pr_head_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "branch": "feat/c2pro-dev-02-role-authority-v1",
        "pr_base_branch": "main",
        "pr_state": "merged",
        "merge_commit_sha": "f00baaf00baaf00baaf00baaf00baaf00baaf00b",
        "authoritative_main_sha": "3fa846d60cecd14239ddb0a953be5e34bede463d",
        "main_contains_merge_commit": False,  # unreachable!
    }
    ci_evidence = {
        "ci_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "ci_status": "success",
    }

    with pytest.raises(ValidationError, match="is not reachable from the canonical main"):
        reconcile_result(
            valid_worker_result,
            remote_evidence=remote_evidence,
            ci_evidence=ci_evidence,
            control_dir=mock_control_plane,
        )


def test_n_main_advances_after_merge(mock_control_plane, valid_worker_result):
    """Test N: main advances after merge -> baseline correctly uses fetched authoritative main SHA."""
    remote_evidence = {
        "remote_head_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "pr_head_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "branch": "feat/c2pro-dev-02-role-authority-v1",
        "pr_base_branch": "main",
        "pr_state": "merged",
        "merge_commit_sha": "f00baaf00baaf00baaf00baaf00baaf00baaf00b",
        "authoritative_main_sha": "advanced_main_sha_after_rebase_9999999",
        "main_contains_merge_commit": True,
    }
    ci_evidence = {
        "ci_sha": "7c3a8347a5bea0c28f2e540559bd515f9afd282a",
        "ci_status": "success",
    }

    reconcile_result(
        valid_worker_result,
        remote_evidence=remote_evidence,
        ci_evidence=ci_evidence,
        control_dir=mock_control_plane,
    )

    with open(mock_control_plane / "current.yaml", encoding="utf-8") as f:
        curr = yaml.safe_load(f)
    assert curr["baseline"]["main_sha"] == "advanced_main_sha_after_rebase_9999999"
