"""
C2Pro - WBS Domain Enums

Work Breakdown Structure enumerations for node types and statuses.
"""

from enum import StrEnum


class WBSNodeType(StrEnum):
    """WBS Node Type classification."""

    DELIVERABLE = "deliverable"
    WORK_PACKAGE = "work_package"
    ACTIVITY = "activity"
    MILESTONE = "milestone"

    def __str__(self) -> str:
        return self.value


class WBSNodeStatus(StrEnum):
    """WBS Node execution status."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"
    CANCELLED = "cancelled"

    def __str__(self) -> str:
        return self.value
