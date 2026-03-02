"""
PII Anonymization & Audit Trail.

Detects and anonymizes PII entities in text, and provides audit logging
for write operations.
"""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID


class PiiDetector:
    """Detects PII entities in text."""

    # Patterns for common PII types
    _PATTERNS = {
        "EMAIL": re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
        "DNI": re.compile(r'\b\d{8}[A-Z]\b'),
    }

    def detect(self, text: str) -> list[dict[str, Any]]:
        """
        Detects PII entities in the given text.

        Returns a list of dicts with keys: type, start, end, value.
        """
        entities: list[dict[str, Any]] = []

        for pii_type, pattern in self._PATTERNS.items():
            for match in pattern.finditer(text):
                entities.append({
                    "type": pii_type,
                    "start": match.start(),
                    "end": match.end(),
                    "value": match.group(),
                })

        # Sort by start position
        entities.sort(key=lambda e: e["start"])
        return entities


class TextAnonymizationService:
    """Anonymizes detected PII spans in text."""

    def __init__(self, detector: PiiDetector) -> None:
        self.detector = detector

    def anonymize(self, text: str) -> str:
        """
        Replaces all detected PII spans with [REDACTED].
        """
        entities = self.detector.detect(text)

        # Process in reverse order to preserve indices
        result = text
        for entity in reversed(entities):
            result = result[:entity["start"]] + "[REDACTED]" + result[entity["end"]:]

        return result


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
        """
        Logs a write operation for audit trail purposes.
        """
        if self.logger:
            self.logger.info(
                "audit_write_operation",
                tenant_id=tenant_id,
                action_type=action_type,
                entity_type=entity_type,
                entity_id=entity_id,
            )
