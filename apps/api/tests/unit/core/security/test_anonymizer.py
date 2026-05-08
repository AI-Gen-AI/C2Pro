"""Security anonymizer unit coverage.

Test Suite ID: TASK-OPS-DOCFLOW-013
"""

from uuid import uuid4

from src.core.security.anonymizer import (
    AuditTrailService,
    PiiDetector,
    TextAnonymizationService,
)


class _Logger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def info(self, event: str, **fields: object) -> None:
        self.events.append((event, fields))


def test_pii_detector_returns_email_and_dni_spans_in_text_order() -> None:
    """TASK-OPS-DOCFLOW-013: detector returns typed PII spans sorted by position."""
    detector = PiiDetector()

    entities = detector.detect("DNI 12345678Z belongs to pm@example.com.")

    assert [entity["type"] for entity in entities] == ["DNI", "EMAIL"]
    assert [entity["value"] for entity in entities] == ["12345678Z", "pm@example.com"]
    assert all(entity["start"] < entity["end"] for entity in entities)


def test_text_anonymization_replaces_detected_spans_without_index_drift() -> None:
    """TASK-OPS-DOCFLOW-013: anonymizer redacts multiple detected PII spans."""
    service = TextAnonymizationService(PiiDetector())

    anonymized = service.anonymize(
        "Send report to pm@example.com and validate DNI 12345678Z."
    )

    assert anonymized == "Send report to [REDACTED] and validate DNI [REDACTED]."
    assert "pm@example.com" not in anonymized
    assert "12345678Z" not in anonymized


def test_audit_trail_service_logs_write_operation_with_tenant_context() -> None:
    """TASK-OPS-DOCFLOW-013: write audit log records tenant/action/entity context."""
    logger = _Logger()
    service = AuditTrailService(logger=logger)
    tenant_id = uuid4()
    entity_id = uuid4()

    service.log_write_operation(
        tenant_id=tenant_id,
        action_type="update",
        entity_type="document",
        entity_id=entity_id,
    )

    assert logger.events == [
        (
            "audit_write_operation",
            {
                "tenant_id": tenant_id,
                "action_type": "update",
                "entity_type": "document",
                "entity_id": entity_id,
            },
        )
    ]
