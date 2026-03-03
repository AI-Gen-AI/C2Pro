"""
Refers to Suite ID: TS-E2E-FLW-BLK-001

Shared in-memory bulk operation job store.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

_jobs: dict[str, dict[str, Any]] = {}


def register_job(job_id: str, job_data: dict[str, Any]) -> None:
    """Register or replace a bulk-operation job payload."""
    payload = dict(job_data)
    now_iso = datetime.now(UTC).isoformat()
    payload.setdefault("status", "queued")
    payload.setdefault("percentage", 0)
    payload.setdefault("processed_items", 0)
    payload.setdefault("total_items", 0)
    payload.setdefault("eta_seconds", 0)
    payload.setdefault("started_at", now_iso)
    payload.setdefault("updated_at", now_iso)
    _jobs[job_id] = payload


def get_job(job_id: str) -> dict[str, Any] | None:
    """Fetch a bulk-operation job by ID."""
    return _jobs.get(job_id)

