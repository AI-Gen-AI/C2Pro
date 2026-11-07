"""Authenticated read boundary for the historical-risk advisory planner.

This boundary deliberately owns no authority flags: its repository derives all
scope and artifact lifecycle facts from persisted state.  It is read-only; the
planner it invokes remains advisory-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from src.analysis.application.historical_risk_alert_reconciliation import (
    ReconciliationInput,
    ReconciliationPlan,
    plan_historical_risk_alert_reconciliation,
)


@dataclass(frozen=True)
class ReconciliationReadScope:
    """Exact selector supplied by an authenticated tenant-scoped caller."""

    tenant_id: UUID
    project_id: UUID
    document_id: UUID
    revision_id: UUID
    artifact_id: UUID


class ReconciliationScopeNotAuthorized(PermissionError):
    """The requested scope is not visible to the authenticated tenant."""


class HistoricalRiskAlertReconciliationReader(Protocol):
    """Read-only source of planner input for one exact authenticated scope."""

    async def assemble(self, scope: ReconciliationReadScope) -> ReconciliationInput: ...


class HistoricalRiskAlertReconciliationService:
    """Delegate an authenticated read snapshot to the pure advisory planner."""

    def __init__(self, reader: HistoricalRiskAlertReconciliationReader) -> None:
        self._reader = reader

    async def plan(self, scope: ReconciliationReadScope) -> ReconciliationPlan:
        if not isinstance(scope, ReconciliationReadScope):
            raise TypeError("scope must be ReconciliationReadScope")
        input_data = await self._reader.assemble(scope)
        return plan_historical_risk_alert_reconciliation(input_data)


__all__ = [
    "HistoricalRiskAlertReconciliationReader",
    "HistoricalRiskAlertReconciliationService",
    "ReconciliationReadScope",
    "ReconciliationScopeNotAuthorized",
]
