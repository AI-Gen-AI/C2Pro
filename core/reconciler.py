"""Canonical Control-Plane Reconciler for C2Pro (G2)."""
from __future__ import annotations

import datetime
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from core.result_parser import extract_result_block, parse_result_yaml, validate_result


class ReconciliationError(Exception):
    """Base exception for reconciliation errors."""


class ValidationError(ReconciliationError):
    """Error during result or evidence validation."""


def default_now_fn() -> str:
    """Returns the current timezone-aware ISO datetime in UTC."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def reconcile_result(
    result_text: str,
    remote_evidence: dict[str, Any],
    ci_evidence: dict[str, Any],
    control_dir: Path | None = None,
    now_fn: Callable[[], str] | None = None
) -> dict[str, Any]:
    """Reconciles accepted worker result evidence into canonical .c2pro control state.

    Args:
        result_text: Fenced YAML block containing the c2pro-implementation-result-v1.
        remote_evidence: Dict containing actual remote Git / PR state.
            Expected keys:
              - 'branch': actual remote branch name
              - 'remote_head_sha': actual SHA of remote branch (worker HEAD)
              - 'pr_head_sha': actual SHA of Pull Request on GitHub (must match remote_head_sha)
              - 'pr_base_sha': immutable baseline base SHA of the PR
              - 'pr_base_branch': base branch of the PR (must be 'main')
              - 'pr_state': state of PR ('open', 'closed_unmerged', 'merged')
              - 'merge_commit_sha': commit SHA of merge result in main
              - 'authoritative_main_sha': fetched SHA of canonical main branch after merge
              - 'main_contains_merge_commit': bool indicating reachability of merge commit in main
        ci_evidence: Dict containing CI build state.
            Expected keys:
              - 'ci_sha': the commit SHA verified by CI (must match worker HEAD)
              - 'ci_status': 'success' / 'passed' or failure
        control_dir: Optional custom Path to .c2pro/control/
        now_fn: Optional clock provider function returning string ISO-8601 timestamp

    Returns:
        Dict representing the reconciliation outcome.
    """
    if now_fn is None:
        now_fn = default_now_fn

    # Locate control directory
    if control_dir is None:
        control_dir = Path(__file__).resolve().parent.parent / ".c2pro" / "control"

    # 1. Check for incomplete transaction BEFORE performing any operations
    tx_path = control_dir / "reconciliation-transaction.yaml"
    if tx_path.exists():
        try:
            with open(tx_path, encoding="utf-8") as f:
                tx_data = yaml.safe_load(f) or {}
            # If there's an incomplete prepared transaction, fail closed
            if tx_data.get("state") == "prepared":
                raise ReconciliationError(
                    f"Incomplete transaction detected for work '{tx_data.get('work_id')}' in prepared state. System state is unverified."
                )
        except (OSError, yaml.YAMLError) as e:
            raise ReconciliationError(f"Failed to read existing transaction: {e}") from e

    # 2. Parse and extract result
    try:
        yaml_block = extract_result_block(result_text)
        result = parse_result_yaml(yaml_block)
    except (OSError, ValueError, TypeError) as e:
        raise ValidationError(f"Malformed implementation-result YAML: {e}") from e

    # 3. Schema validation
    try:
        validate_result(result)
    except (ValidationError, ValueError, TypeError) as e:
        raise ValidationError(f"Result schema validation failed: {e}") from e

    # Validate pr_url specifically for G2
    pr_url = result.get("pr_url")
    if not pr_url or not isinstance(pr_url, str) or not pr_url.startswith(("http://", "https://")):
        raise ValidationError(f"Invalid or missing pr_url: {pr_url!r}")

    work_id = result["work_id"]
    worker_head_sha = result["head_sha"]
    branch = result["branch"]

    # 4. G. Unknown work_id validation
    wq_path = control_dir / "work-queue.yaml"
    if not wq_path.exists():
        raise ValidationError("Missing .c2pro/control/work-queue.yaml")

    try:
        with open(wq_path, encoding="utf-8") as f:
            wq_data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as e:
        raise ReconciliationError(f"Failed to load work-queue.yaml: {e}") from e

    # Load reconciliation history
    history_path = control_dir / "reconciliation-history.yaml"
    completed_work: dict[str, Any] = {}
    if history_path.exists():
        try:
            with open(history_path, encoding="utf-8") as f:
                history_data = yaml.safe_load(f) or {}
                completed_work = history_data.get("completed_work", {})
        except (OSError, yaml.YAMLError) as e:
            raise ReconciliationError(f"Failed to load reconciliation-history.yaml: {e}") from e

    # ==========================================
    # FULL VALIDATION FOR NEW AND REPLAY RUNS
    # ==========================================

    # A. Prove remote/PR head publication match
    remote_head_sha = remote_evidence.get("remote_head_sha")
    pr_head_sha = remote_evidence.get("pr_head_sha")

    if worker_head_sha != remote_head_sha:
        raise ValidationError(f"Remote HEAD mismatch: result head '{worker_head_sha}' != actual remote HEAD '{remote_head_sha}'")
    if worker_head_sha != pr_head_sha:
        raise ValidationError(f"PR HEAD mismatch: result head '{worker_head_sha}' != actual PR HEAD '{pr_head_sha}'")

    # Prove branch matches
    actual_branch = remote_evidence.get("branch")
    if branch != actual_branch:
        raise ValidationError(f"Branch mismatch: result branch '{branch}' != actual branch '{actual_branch}'")

    # B. base_sha validation (Base SHA must be authoritative!)
    pr_base_sha = remote_evidence.get("pr_base_sha")
    result_base_sha = result.get("base_sha")
    if result_base_sha != pr_base_sha:
        raise ValidationError(f"Base SHA mismatch: result base '{result_base_sha}' != actual PR base '{pr_base_sha}'")

    # C. Prove CI freshness
    ci_sha = ci_evidence.get("ci_sha")
    ci_status = ci_evidence.get("ci_status")

    if ci_sha != worker_head_sha:
        raise ValidationError(f"Stale CI SHA: CI verified '{ci_sha}', but verified HEAD is '{worker_head_sha}'")
    if ci_status not in ["success", "passed"]:
        raise ValidationError(f"CI status check failed: CI run on verified SHA '{worker_head_sha}' must be 'success' or 'passed', got '{ci_status}'")

    # PR base branch must be 'main'
    pr_base_branch = remote_evidence.get("pr_base_branch")
    if pr_base_branch != "main":
        raise ValidationError(f"PR for work '{work_id}' base branch must be 'main', got {pr_base_branch!r}. Reconciliation failed.")

    # PR state checks
    pr_state = remote_evidence.get("pr_state")
    if pr_state == "open":
        # Hot state must not advance before merge! Return AWAITING_MERGE, zero mutation
        return {
            "status": "AWAITING_MERGE",
            "message": f"PR for work '{work_id}' is still OPEN. Awaiting merge.",
            "work_id": work_id,
            "idempotent": False,
        }
    elif pr_state == "closed_unmerged":
        raise ValidationError(f"PR for work '{work_id}' was closed without being merged. Reconciliation failed.")
    elif pr_state == "merged":
        pass
    else:
        raise ValidationError(f"Invalid PR state: {pr_state!r}")

    # Validate merge_commit_sha and main reachability
    merge_commit_sha = remote_evidence.get("merge_commit_sha")
    if not merge_commit_sha:
        raise ValidationError("Missing merge_commit_sha in remote evidence.")

    main_contains_merge_commit = remote_evidence.get("main_contains_merge_commit")
    if not main_contains_merge_commit:
        raise ValidationError(f"Merge commit '{merge_commit_sha}' is not reachable from the canonical main branch history. Reconciliation failed.")

    # Retrieve authoritative main SHA after merge
    authoritative_main_sha = remote_evidence.get("authoritative_main_sha")
    if not authoritative_main_sha:
        raise ValidationError("Missing authoritative_main_sha in remote evidence.")

    # H. Duplicate reconciliation / idempotent check for already closed work
    if work_id in completed_work:
        recorded_worker_head = completed_work[work_id].get("worker_head_sha") or completed_work[work_id].get("head_sha")
        recorded_merge_commit = completed_work[work_id].get("merge_commit_sha")
        recorded_main_sha = completed_work[work_id].get("main_sha_after_merge")

        # Full match is required for idempotent replay!
        if (
            recorded_worker_head != worker_head_sha or
            recorded_merge_commit != merge_commit_sha or
            recorded_main_sha != authoritative_main_sha
        ):
            raise ValidationError(
                f"Work '{work_id}' is already closed with conflicting merge evidence. "
                f"Recorded worker head: '{recorded_worker_head}', merge commit: '{recorded_merge_commit}', main: '{recorded_main_sha}'. "
                f"Incoming worker head: '{worker_head_sha}', merge commit: '{merge_commit_sha}', main: '{authoritative_main_sha}'."
            )

        # Idempotent replay matches perfectly, return success without mutation
        return {
            "status": "success",
            "message": f"Idempotent: Work '{work_id}' is already reconciled. No state changes made.",
            "work_id": work_id,
            "idempotent": True,
        }

    # Find work item in queue
    items = wq_data.get("items", [])
    work_item = next((item for item in items if item.get("work_id") == work_id), None)
    if not work_item:
        raise ValidationError(f"Unknown work_id: '{work_id}' is not registered in the active work queue.")

    # Process and classify findings based on Quality Delta Rule
    findings = result.get("findings", [])
    baseline_findings = []
    new_findings = []
    for f in findings:
        if f.startswith("BASELINE_FINDING:"):
            baseline_findings.append(f[len("BASELINE_FINDING:"):].strip())
        elif f.startswith("NEW_FINDING:"):
            new_findings.append(f[len("NEW_FINDING:"):].strip())
        else:
            new_findings.append(f.strip())

    # ==========================================
    # ATOMIC TRANSACTION STAGING & WRITES
    # ==========================================

    # Step 1. Prepare in-memory YAML documents
    # Build updated work-queue.yaml
    new_wq_data = wq_data.copy()
    new_wq_data["items"] = [item for item in items if item.get("work_id") != work_id]

    # Build updated current.yaml
    current_path = control_dir / "current.yaml"
    if current_path.exists():
        try:
            with open(current_path, encoding="utf-8") as f:
                new_current_data = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError) as e:
            raise ReconciliationError(f"Failed to read current.yaml: {e}") from e
    else:
        new_current_data = {}

    new_current_data.setdefault("baseline", {})["main_sha"] = authoritative_main_sha
    active_work = new_current_data.get("active_work", [])
    new_current_data["active_work"] = [wid for wid in active_work if wid != work_id]

    # Build updated reconciliation-history.yaml
    new_completed_work = completed_work.copy()
    new_completed_work[work_id] = {
        "worker_head_sha": worker_head_sha,
        "pr_url": pr_url,
        "merge_commit_sha": merge_commit_sha,
        "main_sha_after_merge": authoritative_main_sha,
        "ci_sha": ci_sha,
        "baseline_findings": baseline_findings,
        "new_findings": new_findings,
        "reconciled_at": now_fn(),
    }
    new_history_content = {
        "schema": "c2pro-reconciliation-history-v1",
        "schema_version": 1,
        "completed_work": new_completed_work,
    }

    # Step 2. Create the PREPARE transaction marker
    tx_content = {
        "schema": "c2pro-reconciliation-transaction-v1",
        "schema_version": 1,
        "work_id": work_id,
        "state": "prepared",
        "worker_head_sha": worker_head_sha,
        "merge_commit_sha": merge_commit_sha,
        "authoritative_main_sha": authoritative_main_sha,
    }
    try:
        with open(tx_path, "w", encoding="utf-8", newline="\n") as f:
            yaml.dump(tx_content, f, sort_keys=False)
    except OSError as e:
        raise ReconciliationError(f"Failed to write transaction marker: {e}") from e

    # Step 3. Write all files to temporary staged files
    wq_path_tmp = Path(str(wq_path) + ".tmp")
    current_path_tmp = Path(str(current_path) + ".tmp")
    history_path_tmp = Path(str(history_path) + ".tmp")

    try:
        # Write work-queue tmp
        with open(wq_path_tmp, "w", encoding="utf-8", newline="\n") as f:
            yaml.dump(new_wq_data, f, sort_keys=False)

        # Write current tmp
        with open(current_path_tmp, "w", encoding="utf-8", newline="\n") as f:
            yaml.dump(new_current_data, f, sort_keys=False)

        # Write history tmp
        with open(history_path_tmp, "w", encoding="utf-8", newline="\n") as f:
            yaml.dump(new_history_content, f, sort_keys=False)

    except OSError as e:
        # Cleanup temporary files on write failure
        for p in (wq_path_tmp, current_path_tmp, history_path_tmp):
            try:
                if p.exists():
                    p.unlink()
            except OSError:
                pass
        raise ReconciliationError(f"Failed staging temporary reconciliation files: {e}") from e

    # Step 4. Atomically replace staged files
    try:
        os.replace(wq_path_tmp, wq_path)
        os.replace(current_path_tmp, current_path)
        os.replace(history_path_tmp, history_path)
    except OSError as e:
        raise ReconciliationError(f"Atomic replacement of control files failed: {e}") from e

    # Step 5. COMMIT -> Delete transaction marker on success
    try:
        if tx_path.exists():
            tx_path.unlink()
    except OSError as e:
        raise ReconciliationError(f"Failed to clear transaction marker: {e}") from e

    return {
        "status": "RECONCILED",
        "message": f"Successfully reconciled work '{work_id}' with merge commit '{merge_commit_sha}' into main '{authoritative_main_sha}'.",
        "work_id": work_id,
        "head_sha": worker_head_sha,
        "idempotent": False,
        "baseline_findings": baseline_findings,
        "new_findings": new_findings,
    }
