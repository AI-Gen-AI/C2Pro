"""
Alert DTO Mappers.

Provides centralized mapping between domain entities and DTOs.
This separates transformation logic from use cases, following hexagonal architecture.
Refers to Suite ID: TS-BUG-ALRT-IMPORT-001.
"""

from uuid import UUID

from src.alerts.application.dtos import AlertResponse
from src.alerts.domain.models import Alert


class AlertMapper:
    """Maps Alert domain entities to AlertResponse DTOs."""

    @staticmethod
    def _detection_evidence(metadata: dict[str, object]) -> dict[str, object] | None:
        """Return detector provenance without conflating reviewer evidence lists."""
        evidence = metadata.get("detection_evidence")
        if isinstance(evidence, dict):
            return evidence

        # Compatibility with historical detector payloads. Reviewer evidence is
        # stored as a list, so only dict-shaped legacy values can be detector
        # provenance.
        legacy = metadata.get("evidence")
        if isinstance(legacy, dict):
            return legacy
        legacy_coherence = metadata.get("coherence_evidence")
        if isinstance(legacy_coherence, dict):
            return legacy_coherence
        return None

    @staticmethod
    def to_response(alert: Alert, tenant_id: UUID) -> AlertResponse:
        """
        Convert domain Alert to AlertResponse DTO.

        Args:
            alert: Domain Alert entity
            tenant_id: Tenant identifier for response

        Returns:
            AlertResponse DTO
        """
        sla_policy_name, sla_due_at = alert.calculate_sla_due_at()
        metadata = Alert.normalize_metadata(alert.alert_metadata)
        return AlertResponse.model_validate(
            {
                "id": alert.id,
                "project_id": alert.project_id,
                "tenant_id": tenant_id,
                "rule_code": alert.rule_id or "AI_EXTRACTED",
                "category": Alert.coerce_category(alert.category),
                "severity": alert.severity.value
                if hasattr(alert.severity, "value")
                else str(alert.severity),
                "message": Alert.coerce_text(alert.title, alert.description, "Untitled alert"),
                "status": alert.status.value
                if hasattr(alert.status, "value")
                else str(alert.status),
                "affected_entities": Alert.normalize_affected_entities(alert.affected_entities),
                "source_clause_id": alert.source_clause_id,
                "detection_evidence": AlertMapper._detection_evidence(metadata),
                "reviewed_by": alert.reviewed_by,
                "reviewed_at": alert.reviewed_at,
                "root_cause": metadata.get("root_cause"),
                "sla_policy_name": sla_policy_name,
                "sla_due_at": sla_due_at,
                "created_at": Alert.coerce_datetime(alert.created_at),
            }
        )

    @staticmethod
    def to_response_list(alerts: list[Alert], tenant_id: UUID) -> list[AlertResponse]:
        """
        Convert a list of Alert entities to AlertResponse DTOs.

        Args:
            alerts: List of domain Alert entities
            tenant_id: Tenant identifier for response

        Returns:
            List of AlertResponse DTOs
        """
        return [AlertMapper.to_response(alert, tenant_id) for alert in alerts]
