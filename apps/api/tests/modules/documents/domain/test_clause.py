"""
Clause Entity Tests (TDD - RED Phase)

Refers to Suite ID: TS-UD-DOC-CLS-001.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.documents.domain.entities.clause import Clause
from src.documents.domain.exceptions import DomainValidationError
from src.documents.domain.events import ClauseEntitiesExtracted


class TestClauseEntity:
    """Refers to Suite ID: TS-UD-DOC-CLS-001."""

    def test_missing_content_raises_validation_error(self):
        """
        Creating a Clause without content must raise DomainValidationError.
        """
        with pytest.raises(DomainValidationError):
            Clause(
                clause_id=uuid4(),
                document_id=uuid4(),
                tenant_id=uuid4(),
                content="",
                clause_type="scope",
                confidence_score=0.9,
            )

    def test_confidence_score_must_be_between_0_and_1(self):
        """
        confidence_score outside [0.0, 1.0] must raise DomainValidationError.
        """
        with pytest.raises(DomainValidationError):
            Clause(
                clause_id=uuid4(),
                document_id=uuid4(),
                tenant_id=uuid4(),
                content="Some content",
                clause_type="scope",
                confidence_score=1.1,
            )

        with pytest.raises(DomainValidationError):
            Clause(
                clause_id=uuid4(),
                document_id=uuid4(),
                tenant_id=uuid4(),
                content="Some content",
                clause_type="scope",
                confidence_score=-0.1,
            )

    def test_missing_document_or_tenant_id_is_invalid(self):
        """
        Clause must have valid document_id and tenant_id.
        """
        with pytest.raises(DomainValidationError):
            Clause(
                clause_id=uuid4(),
                document_id=None,
                tenant_id=uuid4(),
                content="Some content",
                clause_type="scope",
                confidence_score=0.9,
            )

        with pytest.raises(DomainValidationError):
            Clause(
                clause_id=uuid4(),
                document_id=uuid4(),
                tenant_id=None,
                content="Some content",
                clause_type="scope",
                confidence_score=0.9,
            )

    def test_extract_entities_triggers_event(self, mocker):
        """
        extract_entities should trigger ClauseEntitiesExtracted event.
        """
        clause = Clause(
            clause_id=uuid4(),
            document_id=uuid4(),
            tenant_id=uuid4(),
            content="Payment terms within 30 days.",
            clause_type="payment",
            confidence_score=0.95,
        )
        extractor = mocker.Mock()
        extractor.extract.return_value = [{"type": "DATE", "value": "30 days"}]

        clause.extract_entities(extractor=extractor)

        extractor.extract.assert_called_once_with(clause.content)
        assert any(
            isinstance(event, ClauseEntitiesExtracted) for event in clause.events
        )
