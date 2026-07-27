"""FROZEN — ProjectState entity lifecycle (ADR-014 / TASK-V3-014-01).

Governs every canonical project-state entity. Atomic batch supersession is keyed
by ``extraction_run_id`` (a new run's entities go ACTIVE; the prior run's go
SUPERSEDED) — see ADR-014 / the ADR-011 evidence lifecycle this mirrors.
"""

from __future__ import annotations

from enum import StrEnum


class LifecycleStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


__all__ = ["LifecycleStatus"]
