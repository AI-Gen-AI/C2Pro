"""
Resolve Alert Use Case.

Use case for resolving alerts with validation.
"""
from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from fastapi import HTTPException

from alerts.application.dtos import AlertResponse
from alerts.application.mappers import AlertMapper
from alerts.application.ports.alert_repository import IAlertRepository
from alerts.domain.enums import AlertSeverity
from alerts.domain.models import Alert


class AlertNotFoundError(Exception):
    """Raised when alert is not found."""
    pass


class ResolutionValidationError(Exception):
    """Raised when resolution validation fails."""
    pass


class ResolveAlertUseCase:
    MIN_RESOLUTION_LENGTH = {
        AlertSeverity.CRITICAL: 50,
        AlertSeverity.HIGH: 20,
        AlertSeverity.MEDIUM: 10,
        AlertSeverity.LOW: 0,
    }

    def __init__(self, repository: IAlertRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        alert_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        resolution: str,
        root_cause: str | None = None,
    ) -> AlertResponse:
        """Resolve an alert with validation."""
        alert = await self._repository.get_by_id(alert_id, tenant_id)
        if not alert:
            raise AlertNotFoundError(f"Alert {alert_id} not found")

        self._validate_resolution(alert, resolution, root_cause)

        normalized_root_cause = (root_cause or "").strip() or None
        alert.apply_resolution(user_id, resolution, normalized_root_cause)
        alert.append_history(
            "resolved",
            user_id,
            resolution=resolution,
            root_cause=normalized_root_cause or "",
        )

        await self._repository.save(alert)
        await self._repository.commit()

        return AlertMapper.to_response(alert, tenant_id)

    def _validate_resolution(
        self,
        alert: Alert,
        resolution: str,
        root_cause: str | None,
    ) -> None:
        """Validate resolution meets requirements."""
        severity = alert.severity
        minimum_length = self.MIN_RESOLUTION_LENGTH.get(severity, 0)

        if len(resolution.strip()) < minimum_length:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Resolution notes must be at least {minimum_length} characters for {severity.value} alerts",
            )

        if alert.requires_root_cause() and not root_cause:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Root cause is required for high or critical alerts",
            )
