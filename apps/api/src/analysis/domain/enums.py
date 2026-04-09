"""
Domain enums for Analysis module.
"""
from enum import Enum

from src.shared_kernel.enums import AlertSeverity, AlertStatus, AlertType  # noqa: F401 — re-export


class AnalysisType(str, Enum):
    COHERENCE = "coherence"
    RISK = "risk"
    COST = "cost"
    SCHEDULE = "schedule"
    QUALITY = "quality"

class AnalysisStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"
