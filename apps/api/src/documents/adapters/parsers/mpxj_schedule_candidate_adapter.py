"""Optional MPXJ reader for immutable schedule *candidates*, not trusted state.

I-01 (research branch): This module is deliberately NOT wired into upload
policy, ingestion, N4/N12, ProjectGraph or schedule baseline promotion.

Only non-confidential fixtures belong in tests. The reader verifies pinned
bytes and retains source-native dates/IDs without asserting calendars, WBS
authority, or contractual schedule compliance.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import tempfile
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

SUPPORTED_EXTENSIONS = frozenset({".mpp", ".xer"})
MAX_FILE_BYTES = 24 * 1024 * 1024
MAX_TASK_RECORDS = 25_000
JVM_START_LOCK = threading.Lock()


class ScheduleCandidateError(ValueError):
    """Fail-closed import error: no source activity may become trusted."""


@dataclass(frozen=True)
class ScheduleSourceScope:
    tenant_id: UUID
    project_id: UUID
    document_id: UUID
    revision_id: UUID

    def __post_init__(self) -> None:
        for name in ("tenant_id", "project_id", "document_id", "revision_id"):
            if not isinstance(getattr(self, name), UUID):
                raise ScheduleCandidateError("schedule source scope requires UUID fields")


def _read_mpxj_project(source_file: Path) -> Any:
    """Lazy optional dependency: no JVM starts on ordinary API imports."""
    try:
        import jpype
        with JVM_START_LOCK:
            if not jpype.isJVMStarted():
                jpype.startJVM(convertStrings=True)
        from org.mpxj.reader import UniversalProjectReader
        project = UniversalProjectReader().read(str(source_file))
    except (ImportError, OSError, RuntimeError, Exception) as exc:
        # Only expose the exception *class*: provider diagnostics may contain
        # private filesystem paths or embedded project metadata.
        raise ScheduleCandidateError(
            f"MPXJ reader unavailable or unable to parse source ({type(exc).__name__})"
        ) from None
    if project is None:
        raise ScheduleCandidateError("MPXJ returned no project")
    return project


def _source_value(value: Any) -> str | None:
    if value is None:
        return None
    output = str(value).strip()
    return output or None


def _candidate_rows(project: Any) -> tuple[list[dict[str, Any]], dict[str, int]]:
    raw_tasks = list(project.getTasks())
    if len(raw_tasks) > MAX_TASK_RECORDS:
        raise ScheduleCandidateError("schedule task-count limit exceeded")

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    missing_dates = 0
    total_links = 0
    for task in raw_tasks:
        name = _source_value(task.getName())
        if name is None:
            continue
        if len(name) > 1024:
            raise ScheduleCandidateError("schedule task name exceeds safety bound")
        uid = _source_value(task.getUniqueID())
        if uid is None:
            raise ScheduleCandidateError("schedule task has no native unique ID")
        if uid in seen:
            raise ScheduleCandidateError("schedule contains duplicate native task ID")
        seen.add(uid)
        # Native local datetimes are preserved *as source observations*. A
        # time zone and an approved contractual baseline are not inferred.
        start_source = _source_value(task.getStart())
        finish_source = _source_value(task.getFinish())
        if not start_source or not finish_source:
            missing_dates += 1
        pred_ids: list[str] = []
        for relation in task.getPredecessors() or []:
            predecessor = relation.getPredecessorTask()
            pred_uid = _source_value(
                predecessor.getUniqueID() if predecessor is not None else None
            )
            if pred_uid is None:
                raise ScheduleCandidateError("predecessor relation lacks native task ID")
            pred_ids.append(pred_uid)
        total_links += len(pred_ids)
        rows.append({
            "source_locator": f"MPXJ:task_uid:{uid}",
            "source_activity_id": uid,
            "task": name,
            "start_source_local": start_source,
            "end_source_local": finish_source,
            "source_wbs_code": _source_value(task.getWBS()),
            "predecessor_source_ids": pred_ids,
            "duration_source": _source_value(task.getDuration()),
            "milestone_source": bool(task.getMilestone()),
            "wbs_node_id": None,
            "approved_wbs_baseline_id": None,
            "date_state": "NOT_ASSESSED",
            "review_state": "CANDIDATE_UNVALIDATED",
        })
    if not rows:
        raise ScheduleCandidateError("schedule has no named activities")

    stats = {
        "raw_task_records": len(raw_tasks),
        "candidate_activities": len(rows),
        "candidate_predecessor_links": total_links,
        "activities_with_missing_source_dates": missing_dates,
        "calendars_seen": len(project.getCalendars()),
        "resources_seen": len(project.getResources()),
    }
    return rows, stats


def parse_verified_mpxj_candidates(
    *,
    source_bytes: bytes,
    expected_sha256: str,
    file_extension: str,
    scope: ScheduleSourceScope,
    reader: Callable[[Path], Any] | None = None,
) -> dict[str, Any]:
    """Convert pinned MPP/XER bytes to read-only, tenant-scoped observations.

    The output is deliberately NOT the accepted ExcelFileParser schedule schema,
    so it cannot accidentally bypass the approved WBS scope gate.
    """
    if not isinstance(scope, ScheduleSourceScope):
        raise ScheduleCandidateError("verified schedule scope is required")
    suffix = file_extension.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ScheduleCandidateError("unsupported native schedule format")
    if not isinstance(source_bytes, bytes) or not source_bytes:
        raise ScheduleCandidateError("nonempty immutable source bytes required")
    if len(source_bytes) > MAX_FILE_BYTES:
        raise ScheduleCandidateError("native schedule source exceeds size limit")
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise ScheduleCandidateError("invalid source SHA256")
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    if not hmac.compare_digest(source_sha, expected_sha256.lower()):
        raise ScheduleCandidateError("source revision SHA256 mismatch")

    with tempfile.TemporaryDirectory(prefix="c2pro-mpxj-candidate-") as tmp:
        source_path = Path(tmp) / ("schedule" + suffix)
        source_path.write_bytes(source_bytes)
        project = (reader or _read_mpxj_project)(source_path)
        rows, stats = _candidate_rows(project)
    return {
        "scope": {
            "tenant_id": str(scope.tenant_id),
            "project_id": str(scope.project_id),
            "document_id": str(scope.document_id),
            "revision_id": str(scope.revision_id),
        },
        "source": {
            "format": suffix,
            "sha256": source_sha,
            "reader": "mpxj",
            "basis": "PINNED_SOURCE_BYTES",
        },
        "coverage": {
            **stats,
            "schedule_baseline_verified": False,
            "source_calendar_semantics_verified": False,
            "critical_path_verified": False,
            "wbs_node_authority_verified": False,
        },
        "state": "CANDIDATE_UNVALIDATED",
        "time_assessment": "NOT_ASSESSED",
        "trusted_promotions": 0,
        "effects_allowed": False,
        "activities": rows,
    }


__all__ = [
    "MAX_FILE_BYTES",
    "MAX_TASK_RECORDS",
    "ScheduleCandidateError",
    "ScheduleSourceScope",
    "parse_verified_mpxj_candidates",
]
