"""
PII Anonymization & Audit Tests (TDD - RED Phase)

Refers to Suite ID: TS-UC-SEC-ANO-001.
Refers to Suite ID: TS-UA-SVC-ANO-001.
Refers to Suite ID: TS-UC-SEC-AUD-001.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.core.security.anonymizer import (
    AuditTrailService,
    PiiDetector,
    TextAnonymizationService,
)


class TestPiiDetection:
    """Refers to Suite ID: TS-UC-SEC-ANO-001."""

    def test_detects_email_span_indices(self):
        """
        Triangulation Test 1:
        "Contact me at test@email.com" -> Detects Email with span indices.
        """
        detector = PiiDetector()
        text = "Contact me at test@email.com"

        entities = detector.detect(text)

        assert entities == [
            {
                "type": "EMAIL",
                "start": 14,
                "end": 28,
                "value": "test@email.com",
            }
        ]

    def test_detects_dni_span_indices(self):
        """
        Triangulation Test 2:
        "My ID is 12345678Z" -> Detects DNI with span indices.
        """
        detector = PiiDetector()
        text = "My ID is 12345678Z"

        entities = detector.detect(text)

        assert entities == [
            {
                "type": "DNI",
                "start": 9,
                "end": 18,
                "value": "12345678Z",
            }
        ]


class TestAnonymizationService:
    """Refers to Suite ID: TS-UA-SVC-ANO-001."""

    def test_anonymizes_detected_pii(self, mocker):
        """
        Input text -> output text with [REDACTED].
        """
        detector = mocker.Mock()
        detector.detect.return_value = [
            {"type": "EMAIL", "start": 14, "end": 28, "value": "test@email.com"},
        ]
        service = TextAnonymizationService(detector=detector)
        text = "Contact me at test@email.com"

        result = service.anonymize(text)

        assert result == "Contact me at [REDACTED]"


class TestAuditCore:
    """Refers to Suite ID: TS-UC-SEC-AUD-001."""

    def test_write_operation_creates_audit_log_entry(self, mocker):
        """
        ANY write operation must create audit_logs entry.
        """
        audit_repo = mocker.Mock()
        audit_logger = mocker.Mock()
        service = AuditTrailService(repository=audit_repo, logger=audit_logger)
        tenant_id = uuid4()

        service.log_write_operation(
            tenant_id=tenant_id,
            action_type="update",
            entity_type="project",
            entity_id=uuid4(),
        )

        audit_logger.info.assert_called_once()
        call_kwargs = audit_logger.info.call_args.kwargs
        assert call_kwargs["tenant_id"] == tenant_id
        assert call_kwargs["action_type"] == "update"
