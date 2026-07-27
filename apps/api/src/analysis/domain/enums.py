"""
Domain enums for Analysis module.
"""

from enum import StrEnum

from src.shared_kernel.enums import (
    AlertSeverity as AlertSeverity,
)
from src.shared_kernel.enums import (
    AlertStatus as AlertStatus,
)
from src.shared_kernel.enums import (
    AlertType as AlertType,
)

__all__ = [
    "AlertSeverity",
    "AlertStatus",
    "AlertType",
    "AnalysisType",
    "AnalysisStatus",
]


class AnalysisType(StrEnum):
    COHERENCE = "coherence"
    RISK = "risk"
    COST = "cost"
    SCHEDULE = "schedule"
    QUALITY = "quality"


class AnalysisStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"
