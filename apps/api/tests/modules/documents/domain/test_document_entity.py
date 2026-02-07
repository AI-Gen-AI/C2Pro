"""
TS-UD-DOC-DOC-001: Document Entity tests.
"""

from datetime import datetime
from uuid import uuid4

import pytest

from src.documents.domain.models import Clause, ClauseType, Document, DocumentStatus, DocumentType


class TestDocumentEntity:
    """Refers to Suite ID: TS-UD-DOC-DOC-001"""

    def test_001_document_creation_minimum_fields(self):
        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="contract.pdf",
            upload_status=DocumentStatus.UPLOADED,
        )
        assert doc.filename == "contract.pdf"
        assert doc.document_type == DocumentType.CONTRACT
        assert doc.upload_status == DocumentStatus.UPLOADED
        assert doc.clauses == []

    def test_002_document_creation_all_fields(self):
        now = datetime.utcnow()
        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            document_type=DocumentType.SPECIFICATION,
            filename="specs.docx",
            upload_status=DocumentStatus.PARSED,
            file_format="docx",
            storage_url="/local/specs.docx",
            storage_encrypted=True,
            file_size_bytes=1024,
            parsed_at=now,
            created_by=uuid4(),
            created_at=now,
            updated_at=now,
            document_metadata={"source": "test"},
        )
        assert doc.file_format == "docx"
        assert doc.storage_url == "/local/specs.docx"
        assert doc.parsed_at == now
        assert doc.document_metadata["source"] == "test"

    def test_003_is_parsed_true_when_status_parsed(self):
        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="c.pdf",
            upload_status=DocumentStatus.PARSED,
        )
        assert doc.is_parsed() is True

    def test_004_has_error_true_when_status_error(self):
        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="c.pdf",
            upload_status=DocumentStatus.ERROR,
        )
        assert doc.has_error() is True

    def test_005_clause_count_matches_list(self):
        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="c.pdf",
            upload_status=DocumentStatus.UPLOADED,
        )
        assert doc.clause_count() == 0
        clause = Clause(
            id=uuid4(),
            project_id=doc.project_id,
            document_id=doc.id,
            clause_code="1",
            clause_type=ClauseType.SCOPE,
            title="Scope",
            full_text="Scope text",
        )
        doc.add_clause(clause)
        assert doc.clause_count() == 1

    def test_006_add_clause_rejects_wrong_document(self):
        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="c.pdf",
            upload_status=DocumentStatus.UPLOADED,
        )
        clause = Clause(
            id=uuid4(),
            project_id=doc.project_id,
            document_id=uuid4(),
            clause_code="1",
            clause_type=ClauseType.SCOPE,
            title="Scope",
            full_text="Scope text",
        )
        with pytest.raises(ValueError, match="Clause does not belong to this document"):
            doc.add_clause(clause)

    def test_007_transition_uploaded_to_queued(self):
        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="c.pdf",
            upload_status=DocumentStatus.UPLOADED,
        )
        updated = doc.transition_to(DocumentStatus.QUEUED)
        assert updated.upload_status == DocumentStatus.QUEUED
        assert doc.upload_status == DocumentStatus.UPLOADED

    def test_008_transition_parsing_to_parsed(self):
        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="c.pdf",
            upload_status=DocumentStatus.PARSING,
        )
        updated = doc.transition_to(DocumentStatus.PARSED)
        assert updated.upload_status == DocumentStatus.PARSED

    def test_009_transition_any_to_error(self):
        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="c.pdf",
            upload_status=DocumentStatus.QUEUED,
        )
        updated = doc.transition_to(DocumentStatus.ERROR)
        assert updated.upload_status == DocumentStatus.ERROR

    def test_010_transition_invalid_raises(self):
        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="c.pdf",
            upload_status=DocumentStatus.PARSED,
        )
        with pytest.raises(ValueError, match="Invalid status transition"):
            doc.transition_to(DocumentStatus.QUEUED)
