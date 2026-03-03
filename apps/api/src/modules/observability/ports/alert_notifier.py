"""
I12 Observability Alert Notifier Port
Test Suite IDs: TS-I12-OBS-PORT-001, TS-I12-OBS-APP-006
"""

from typing import Protocol

from src.modules.observability.domain.entities import DriftAlert


class IAlertNotifier(Protocol):
    async def send_escalation_alert(self, alert: DriftAlert) -> None:
        ...
