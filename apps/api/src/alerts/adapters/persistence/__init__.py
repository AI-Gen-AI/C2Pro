"""
Alerts Persistence Layer.

SQLAlchemy implementation of alert repository.
Reuses AlertORM from analysis module for persistence.
Refers to Suite ID: TS-BUG-ALRT-IMPORT-001.
"""
from src.alerts.adapters.persistence.alert_repository import SqlAlchemyAlertRepository

__all__ = ["SqlAlchemyAlertRepository"]
