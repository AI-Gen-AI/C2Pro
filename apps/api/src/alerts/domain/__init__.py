"""
Alerts Domain Layer.

Pure Python domain entities and services - NO SQLAlchemy, NO FastAPI imports.
Refers to TASK-REV-006: Hexagonal Architecture refactoring.
"""

from alerts.domain.enums import AlertSeverity, AlertStatus, ApprovalStatus
from alerts.domain.models import Alert

__all__ = ["Alert", "AlertSeverity", "AlertStatus", "ApprovalStatus"]
