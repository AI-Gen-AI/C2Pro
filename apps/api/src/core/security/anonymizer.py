"""
PII Anonymization & Audit Trail stubs.

These classes are defined to satisfy RED-phase test imports.
Full implementation is pending.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID


class PiiDetector:
    """Detects PII entities in text."""

    def detect(self, text: str) -> list[dict[str, Any]]:
        raise NotImplementedError("PiiDetector.detect not yet implemented")


class TextAnonymizationService:
    """Anonymizes detected PII spans in text."""

    def __init__(self, detector: PiiDetector) -> None:
        self.detector = detector

    def anonymize(self, text: str) -> str:
        raise NotImplementedError("TextAnonymizationService.anonymize not yet implemented")


class AuditTrailService:
    """Creates audit log entries for write operations."""

    def __init__(self, repository: Any = None, logger: Any = None) -> None:
        self.repository = repository
        self.logger = logger

    def log_write_operation(
        self,
        tenant_id: UUID,
        action_type: str,
        entity_type: str,
        entity_id: UUID,
    ) -> None:
        raise NotImplementedError("AuditTrailService.log_write_operation not yet implemented")
