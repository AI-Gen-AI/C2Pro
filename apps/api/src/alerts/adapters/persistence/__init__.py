"""
Alerts Persistence Layer.

SQLAlchemy implementation of alert repository.
Reuses AlertORM from analysis module for persistence.
"""
from alerts.adapters.persistence.alert_repository import SqlAlchemyAlertRepository

__all__ = ["SqlAlchemyAlertRepository"]
