"""Canonical Control-Plane Reconciler for C2Pro (G2)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from core.result_parser import extract_result_block, parse_result_yaml, validate_result


class ReconciliationError(Exception):
    """Base exception for reconciliation errors."""


class ValidationError(ReconciliationError):
    """Error during result or evidence validation."""


def reconcile_result(
    result_text: str,
    remote_evidence: dict[str, Any],
    ci_evidence: dict[str, Any],
    control_dir: Path | None = None
) -> dict[str, Any]:
    """Reconciles accepted worker result evidence into canonical .c2pro control state.

    Args:
        result_text: Fenced YAML block containing the c2pro-implementation-result-v1.
        remote_evidence: Dict containing actual remote Git / PR state.
            Expected keys:
              - 'branch': actual remote branch name
              - 'remote_head_sha': actual SHA of remote branch (worker HEAD)
              - 'pr_head_sha': actual SHA of Pull Request on GitHub (must match remote_head_sha)
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

    Returns:
        Dict representing the reconciliation outcome.
    """
    # 1. Parse and extract result
    try:
        yaml_block = extract_result_block(result_text)
        result = parse_result_yaml(yaml_block)
    except (OSError, ValueError, TypeError) as e:
        raise ValidationError(f"Malformed implementation-result YAML: {e}") from e

    # 2. Schema validation
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

    # Locate control directory
    if control_dir is None:
        control_dir = Path(__file__).resolve().parent.parent / ".c2pro" / "control"

    # G. Unknown work_id validation
    wq_path = control_dir / "work-queue.yaml"
    if not wq_path.exists():
        raise ValidationError("Missing .c2pro/control/work-queue.yaml")

    try:
        with open(wq_path, encoding="utf-8") as f:
            wq_data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as e:
        raise ReconciliationError(f"Failed to load work-queue.yaml: {e}") from e

    # Load reconciliation history to check closed tasks
    history_path = control_dir / "reconciliation-history.yaml"
    completed_work: dict[str, Any] = {}
    if history_path.exists():
        try:
            with open(history_path, encoding="utf-8") as f:
                history_data = yaml.safe_load(f) or {}
                completed_work = history_data.get("completed_work", {})
        except (OSError, yaml.YAMLError) as e:
            raise ReconciliationError(f"Failed to load reconciliation-history.yaml: {e}") from e

    # H. result for already-closed work with conflicting HEAD/merge evidence
    if work_id in completed_work:
        recorded_worker_head = completed_work[work_id].get("worker_head_sha") or completed_work[work_id].get("head_sha")
        recorded_merge_commit = completed_work[work_id].get("merge_commit_sha")
        recorded_main_sha = completed_work[work_id].get("main_sha_after_merge")

        current_merge_commit = remote_evidence.get("merge_commit_sha")
        current_main_sha = remote_evidence.get("authoritative_main_sha")

        if (
            recorded_worker_head != worker_head_sha or
            recorded_merge_commit != current_merge_commit or
            recorded_main_sha != current_main_sha
        ):
            raise ValidationError(
                f"Work '{work_id}' is already closed with conflicting merge evidence. "
                f"Recorded worker head: '{recorded_worker_head}', merge commit: '{recorded_merge_commit}', main: '{recorded_main_sha}'. "
                f"Incoming worker head: '{worker_head_sha}', merge commit: '{current_merge_commit}', main: '{current_main_sha}'."
            )
        # E. Duplicate reconciliation (Idempotency)
        # If all evidence matches, return success with idempotent message
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

    # 3. Prove publication: returned HEAD must match actual remote/PR head
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

    # 4. Prove CI freshness: CI verified SHA must match verified remote HEAD
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

    # Verify PR state and ensure HOT STATE DOES NOT ADVANCE BEFORE MERGE
    pr_state = remote_evidence.get("pr_state")
    if pr_state == "open":
        # Returns AWAITING_MERGE, zero mutation to control files
        return {
            "status": "AWAITING_MERGE",
            "message": f"PR for work '{work_id}' is still OPEN. Awaiting merge.",
            "work_id": work_id,
            "idempotent": False,
        }
    elif pr_state == "closed_unmerged":
        raise ValidationError(f"PR for work '{work_id}' was closed without being merged. Reconciliation failed.")
    elif pr_state == "merged":
        # Proceed with merge verification
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

    # F. Modern result attempting legacy backlog/blackboard write:
    # Ensure we NEVER write to blackboard.json or Markdown files.
    # (The actual logic performs no writes to blackboard/Markdown files, only to .c2pro/control/*)

    # 5. Reconcile accepted evidence into .c2pro/control/*
    # Update work-queue.yaml: remove the completed work item
    wq_data["items"] = [item for item in items if item.get("work_id") != work_id]
    try:
        with open(wq_path, "w", encoding="utf-8", newline="\n") as f:
            yaml.dump(wq_data, f, sort_keys=False)
    except OSError as e:
        raise ReconciliationError(f"Failed to update work-queue.yaml: {e}") from e

    # Update current.yaml: remove from active_work and update baseline main_sha to canonical main SHA
    current_data: dict[str, Any] = {}
    current_path = control_dir / "current.yaml"
    if current_path.exists():
        try:
            with open(current_path, encoding="utf-8") as f:
                current_data = yaml.safe_load(f) or {}

            # Update baseline baseline.main_sha to verified current main SHA (never worker head SHA)
            current_data.setdefault("baseline", {})["main_sha"] = authoritative_main_sha

            # Remove from active_work
            active_work = current_data.get("active_work", [])
            current_data["active_work"] = [wid for wid in active_work if wid != work_id]

            with open(current_path, "w", encoding="utf-8", newline="\n") as f:
                yaml.dump(current_data, f, sort_keys=False)
        except (OSError, yaml.YAMLError) as e:
            raise ReconciliationError(f"Failed to update current.yaml: {e}") from e

    # Record in reconciliation-history.yaml
    completed_work[work_id] = {
        "worker_head_sha": worker_head_sha,
        "pr_url": pr_url,
        "merge_commit_sha": merge_commit_sha,
        "main_sha_after_merge": authoritative_main_sha,
        "ci_sha": ci_sha,
        "baseline_findings": baseline_findings,
        "new_findings": new_findings,
        "reconciled_at": "2026-09-06T22:50:00Z",
    }
    history_content = {
        "schema": "c2pro-reconciliation-history-v1",
        "schema_version": 1,
        "completed_work": completed_work,
    }
    try:
        with open(history_path, "w", encoding="utf-8", newline="\n") as f:
            yaml.dump(history_content, f, sort_keys=False)
    except OSError as e:
        raise ReconciliationError(f"Failed to update reconciliation-history.yaml: {e}") from e

    return {
        "status": "RECONCILED",
        "message": f"Successfully reconciled work '{work_id}' with merge commit '{merge_commit_sha}' into main '{authoritative_main_sha}'.",
        "work_id": work_id,
        "head_sha": worker_head_sha,
        "idempotent": False,
        "baseline_findings": baseline_findings,
        "new_findings": new_findings,
    }
