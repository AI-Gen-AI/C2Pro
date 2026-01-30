"""
Domain enums for Analysis module.
"""
from enum import Enum

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

class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class AlertStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"
