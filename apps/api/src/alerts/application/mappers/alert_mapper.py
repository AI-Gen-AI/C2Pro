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
    def _detection_evidence(
        metadata: dict[str, object], source_clause_id: UUID | None
    ) -> dict[str, object] | None:
        """Return detector provenance without conflating reviewer evidence lists."""
        evidence = metadata.get("detection_evidence")
        if isinstance(evidence, dict):
            return evidence

        provenance = metadata.get("source_provenance")
        if not isinstance(provenance, dict) or provenance.get("verification_status") != "VERIFIED":
            provenance = None
        references = provenance.get("source_references") if provenance is not None else None
        if isinstance(references, list) and len(references) == 1 and source_clause_id is not None:
            reference = references[0]
            if isinstance(reference, dict):
                try:
                    document_id = str(UUID(str(reference.get("document_id"))))
                    revision_id = str(UUID(str(reference.get("revision_id"))))
                    clause_id = UUID(str(reference.get("clause_id")))
                except (TypeError, ValueError):
                    pass
                else:
                    locator = reference.get("clause_code")
                    if clause_id == source_clause_id and isinstance(locator, str) and locator.strip():
                        # This is a revision-bound navigation locator, never a
                        # quoted source statement.
                        return {
                            "source_clause_id": str(clause_id),
                            "source_document_id": document_id,
                            "source_revision_id": revision_id,
                            "source_locator": locator,
                        }

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
                "detection_evidence": AlertMapper._detection_evidence(
                    metadata, alert.source_clause_id
                ),
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
