"""
Shared enums used across bounded contexts.

Canonical definitions — each owning module re-exports for backward
compatibility.
"""

from enum import StrEnum


class AlertSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AlertStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class AlertType(StrEnum):
    """Alert type discriminator (TASK-BCK-026)."""
    RISK = "risk"
    COHERENCE = "coherence"
    BUDGET = "budget"
    WBS = "wbs"
    AUDIT_INCOMPLETE = "audit_incomplete"


class RACIRole(StrEnum):
    RESPONSIBLE = "R"
    ACCOUNTABLE = "A"
    CONSULTED = "C"
    INFORMED = "I"


class WBSItemType(StrEnum):
    DELIVERABLE = "deliverable"
    WORK_PACKAGE = "work_package"
    ACTIVITY = "activity"
