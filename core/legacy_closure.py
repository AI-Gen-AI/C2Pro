"""Legacy machine-derived closure for pre-schema C2Pro development work (G2).

Some canonical work items (e.g. C2PRO-DEV-02, merged as PR #564 on 2026-08-24)
were merged before the c2pro-implementation-result-v1 schema existed
(introduced with G1, PR #597, merged 2026-09-06). No worker ever produced, or
could have produced, a conforming structured result for that work.
Reconstructing one now would fabricate history that never existed.

This module reconciles that class of work using ONLY machine-verifiable
Git/GitHub evidence, on a code path that is structurally separate from
`core.reconciler.reconcile_result` -- a genuine worker self-report -- so a
legacy closure can never be mistaken for one. `core.reconciler` is not
imported or modified by this module.
"""
from __future__ import annotations

import datetime
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from core.result_parser import SHA_RE, WORK_ID_RE


class LegacyClosureError(Exception):
    """Base exception for legacy closure errors."""


class LegacyClosureValidationError(LegacyClosureError):
    """Error validating legacy closure evidence."""


def default_now_fn() -> str:
    """Returns the current timezone-aware ISO datetime in UTC."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


REQUIRED_EVIDENCE_FIELDS = (
    "work_id",
    "branch",
    "base_sha",
    "head_sha",
    "merge_commit_sha",
    "authoritative_main_sha",
    "main_contains_merge_commit",
    "pr_url",
    "pr_state",
    "ci_status",
    "provenance",
)


def validate_legacy_evidence(evidence: dict[str, Any]) -> None:
    """Validates machine-derived closure evidence. Raises on any fabrication risk."""
    if not isinstance(evidence, dict):
        raise TypeError("evidence must be a dictionary")

    if evidence.get("schema") == "c2pro-implementation-result-v1":
        raise LegacyClosureValidationError(
            "Legacy closure evidence MUST NOT declare schema "
            "'c2pro-implementation-result-v1' -- that schema asserts a genuine "
            "worker self-report, which does not exist for pre-schema work. "
            "Use core.reconciler.reconcile_result for real worker results."
        )

    missing = [f for f in REQUIRED_EVIDENCE_FIELDS if evidence.get(f) in (None, "", [], {})]
    if missing:
        raise LegacyClosureValidationError(f"Missing required legacy evidence fields: {missing}")

    work_id = evidence["work_id"]
    if not isinstance(work_id, str) or not WORK_ID_RE.match(work_id):
        raise LegacyClosureValidationError(f"Invalid work_id: {work_id!r}")

    for field in ("base_sha", "head_sha", "merge_commit_sha", "authoritative_main_sha"):
        value = evidence[field]
        if not isinstance(value, str) or not SHA_RE.match(value):
            raise LegacyClosureValidationError(
                f"Invalid {field}: must be a 40-character hex SHA, got {value!r}"
            )

    if evidence["pr_state"] != "merged":
        raise LegacyClosureValidationError(
            f"Legacy closure requires pr_state == 'merged', got {evidence['pr_state']!r}"
        )

    if evidence["main_contains_merge_commit"] is not True:
        raise LegacyClosureValidationError(
            "main_contains_merge_commit must be verified True (the merge commit must "
            "be an ancestor of the canonical main branch) -- refusing to close on an "
            "unverified or negative reachability result"
        )

    provenance = evidence["provenance"]
    if not isinstance(provenance, dict):
        raise LegacyClosureValidationError("provenance must be a dictionary")
    for key in ("derived_from", "reason"):
        if not provenance.get(key):
            raise LegacyClosureValidationError(f"provenance.{key} is required and must be non-empty")


def reconcile_legacy_closure(
    evidence: dict[str, Any],
    control_dir: Path | None = None,
    now_fn: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """Reconciles a pre-schema, already-merged work item using machine-derived
    evidence only.

    Unlike `core.reconciler.reconcile_result`, this function never parses or
    validates a c2pro-implementation-result-v1 block -- none exists for this
    class of work. Every fact in `evidence` must be independently verifiable
    against Git/GitHub. The resulting history entry is tagged
    `closure_type: "legacy_machine_derived"` and carries the evidence's
    `provenance`, so it can never be read back as a genuine worker self-report.
    """
    if now_fn is None:
        now_fn = default_now_fn

    if control_dir is None:
        control_dir = Path(__file__).resolve().parent.parent / ".c2pro" / "control"

    validate_legacy_evidence(evidence)

    work_id = evidence["work_id"]
    head_sha = evidence["head_sha"]
    merge_commit_sha = evidence["merge_commit_sha"]
    authoritative_main_sha = evidence["authoritative_main_sha"]

    # 1. Check for incomplete transaction BEFORE performing any operations.
    #    Shared marker file / fail-closed semantics with core.reconciler so
    #    the two closure paths cannot race each other undetected.
    tx_path = control_dir / "reconciliation-transaction.yaml"
    if tx_path.exists():
        try:
            with open(tx_path, encoding="utf-8") as f:
                tx_data = yaml.safe_load(f) or {}
            if tx_data.get("state") == "prepared":
                raise LegacyClosureError(
                    f"Incomplete transaction detected for work '{tx_data.get('work_id')}' "
                    "in prepared state. System state is unverified."
                )
        except (OSError, yaml.YAMLError) as e:
            raise LegacyClosureError(f"Failed to read existing transaction: {e}") from e

    wq_path = control_dir / "work-queue.yaml"
    if not wq_path.exists():
        raise LegacyClosureValidationError("Missing .c2pro/control/work-queue.yaml")
    try:
        with open(wq_path, encoding="utf-8") as f:
            wq_data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as e:
        raise LegacyClosureError(f"Failed to load work-queue.yaml: {e}") from e

    history_path = control_dir / "reconciliation-history.yaml"
    completed_work: dict[str, Any] = {}
    if history_path.exists():
        try:
            with open(history_path, encoding="utf-8") as f:
                history_data = yaml.safe_load(f) or {}
                completed_work = history_data.get("completed_work", {})
        except (OSError, yaml.YAMLError) as e:
            raise LegacyClosureError(f"Failed to load reconciliation-history.yaml: {e}") from e

    # Idempotent replay / conflict check (checked before queue membership,
    # mirroring core.reconciler.reconcile_result's ordering).
    if work_id in completed_work:
        recorded = completed_work[work_id]
        recorded_head = recorded.get("head_sha") or recorded.get("worker_head_sha")
        if (
            recorded_head != head_sha
            or recorded.get("merge_commit_sha") != merge_commit_sha
            or recorded.get("main_sha_after_merge") != authoritative_main_sha
        ):
            raise LegacyClosureValidationError(
                f"Work '{work_id}' is already closed with conflicting evidence. "
                f"Recorded head: '{recorded_head}', merge commit: "
                f"'{recorded.get('merge_commit_sha')}', main: "
                f"'{recorded.get('main_sha_after_merge')}'. Incoming head: '{head_sha}', "
                f"merge commit: '{merge_commit_sha}', main: '{authoritative_main_sha}'."
            )
        return {
            "status": "success",
            "message": f"Idempotent: work '{work_id}' is already legacy-closed. No state changes made.",
            "work_id": work_id,
            "idempotent": True,
        }

    items = wq_data.get("items", [])
    work_item = next((item for item in items if item.get("work_id") == work_id), None)
    if not work_item:
        raise LegacyClosureValidationError(
            f"Unknown work_id: '{work_id}' is not registered in the active work queue."
        )

    # ==========================================
    # ATOMIC TRANSACTION STAGING & WRITES
    # (mirrors core.reconciler.reconcile_result's atomicity pattern; not
    # imported from it, to keep the two closure paths structurally distinct)
    # ==========================================

    new_wq_data = wq_data.copy()
    new_wq_data["items"] = [item for item in items if item.get("work_id") != work_id]

    current_path = control_dir / "current.yaml"
    if current_path.exists():
        try:
            with open(current_path, encoding="utf-8") as f:
                new_current_data = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError) as e:
            raise LegacyClosureError(f"Failed to read current.yaml: {e}") from e
    else:
        new_current_data = {}

    new_current_data.setdefault("baseline", {})["main_sha"] = authoritative_main_sha
    active_work = new_current_data.get("active_work", [])
    new_current_data["active_work"] = [wid for wid in active_work if wid != work_id]

    new_completed_work = completed_work.copy()
    new_completed_work[work_id] = {
        "closure_type": "legacy_machine_derived",
        "head_sha": head_sha,
        "branch": evidence["branch"],
        "base_sha": evidence["base_sha"],
        "pr_url": evidence["pr_url"],
        "merge_commit_sha": merge_commit_sha,
        "main_sha_after_merge": authoritative_main_sha,
        "ci_status": evidence["ci_status"],
        "provenance": evidence["provenance"],
        "reconciled_at": now_fn(),
    }
    new_history_content = {
        "schema": "c2pro-reconciliation-history-v1",
        "schema_version": 1,
        "completed_work": new_completed_work,
    }

    tx_content = {
        "schema": "c2pro-legacy-closure-transaction-v1",
        "schema_version": 1,
        "work_id": work_id,
        "state": "prepared",
        "head_sha": head_sha,
        "merge_commit_sha": merge_commit_sha,
        "authoritative_main_sha": authoritative_main_sha,
    }
    try:
        with open(tx_path, "w", encoding="utf-8", newline="\n") as f:
            yaml.dump(tx_content, f, sort_keys=False)
    except OSError as e:
        raise LegacyClosureError(f"Failed to write transaction marker: {e}") from e

    wq_path_tmp = Path(str(wq_path) + ".tmp")
    current_path_tmp = Path(str(current_path) + ".tmp")
    history_path_tmp = Path(str(history_path) + ".tmp")

    try:
        with open(wq_path_tmp, "w", encoding="utf-8", newline="\n") as f:
            yaml.dump(new_wq_data, f, sort_keys=False)
        with open(current_path_tmp, "w", encoding="utf-8", newline="\n") as f:
            yaml.dump(new_current_data, f, sort_keys=False)
        with open(history_path_tmp, "w", encoding="utf-8", newline="\n") as f:
            yaml.dump(new_history_content, f, sort_keys=False)
    except OSError as e:
        for p in (wq_path_tmp, current_path_tmp, history_path_tmp):
            try:
                if p.exists():
                    p.unlink()
            except OSError:
                pass
        raise LegacyClosureError(f"Failed staging temporary reconciliation files: {e}") from e

    try:
        os.replace(wq_path_tmp, wq_path)
        os.replace(current_path_tmp, current_path)
        os.replace(history_path_tmp, history_path)
    except OSError as e:
        raise LegacyClosureError(f"Atomic replacement of control files failed: {e}") from e

    try:
        if tx_path.exists():
            tx_path.unlink()
    except OSError as e:
        raise LegacyClosureError(f"Failed to clear transaction marker: {e}") from e

    return {
        "status": "LEGACY_CLOSED",
        "message": (
            f"Legacy-closed work '{work_id}' via machine-derived evidence "
            f"(merge commit '{merge_commit_sha}' into main '{authoritative_main_sha}'). "
            "No worker self-report exists, or was fabricated, for this closure."
        ),
        "work_id": work_id,
        "head_sha": head_sha,
        "idempotent": False,
    }
