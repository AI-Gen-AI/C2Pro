"""
Attach reviewer evidence to an alert.

Detector provenance remains in detection_evidence; this use case appends only
human/reviewer evidence to the reviewer-evidence list and audit history.
"""
from __future__ import annotations

from uuid import UUID

from src.alerts.application.dtos import EvidenceResponse
from src.alerts.application.ports.alert_repository import IAlertRepository


class AlertNotFoundError(Exception):
    """Raised when an alert is not visible in the caller tenant."""


class AttachAlertEvidenceUseCase:
    def __init__(self, repository: IAlertRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        alert_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        evidence_type: str,
        content: str,
        source: str,
    ) -> EvidenceResponse:
        alert = await self._repository.get_by_id(alert_id, tenant_id)
        if alert is None:
            raise AlertNotFoundError(f"Alert {alert_id} not found")

        normalized_content = content.strip()
        if not normalized_content:
            raise ValueError("Evidence content cannot be empty")

        normalized_source = source.strip() or "manual_review"
        alert.attach_evidence(
            evidence_type=evidence_type,
            content=normalized_content,
            source=normalized_source,
            added_by=user_id,
        )
        alert.append_history(
            "evidence_attached",
            user_id,
            evidence_type=evidence_type,
            source=normalized_source,
        )

        await self._repository.save(alert, tenant_id)
        await self._repository.commit()

        raw_evidence = (alert.alert_metadata or {}).get("evidence", [])
        return EvidenceResponse(
            alert_id=str(alert_id),
            evidence_count=len(raw_evidence) if isinstance(raw_evidence, list) else 0,
        )
