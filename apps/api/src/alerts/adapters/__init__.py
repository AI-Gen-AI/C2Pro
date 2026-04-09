"""
Alerts Persistence Adapters.

SQLAlchemy implementation of alert persistence.
"""
from alerts.adapters.persistence.alert_repository import SqlAlchemyAlertRepository

__all__ = ["SqlAlchemyAlertRepository"]
