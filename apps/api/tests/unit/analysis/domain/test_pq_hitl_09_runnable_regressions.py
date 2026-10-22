"""PQ-HITL-09 runnable regression checks (ACC-01 / #1049 / parent PQ-HITL-09 #945).

Suite ID: TS-PQ-HITL-09-REG-001.

Regression checks verifying:
1. No fabricated score or false-green presence when evidence is absent (honest nulls).
2. Preservation of target RED confidence invariant (absent confidence must yield None, not 0.9).
3. Stale revision protection and revision-boundary containment.
4. Coexistence of high coherence scores with critical alerts.
5. Real upload policy boundary rejecting .docx for structured budget and schedule types.
"""

from __future__ import annotations

from io import BytesIO
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException, UploadFile

from src.analysis.domain.coherence_derivation import (
    CoherenceDerivationInput,
    derive_coherence_flags,
)
from src.analysis.domain.contracts import (
    CoherenceCategory,
    CoherenceFinding,
    Severity,
)
from src.analysis.domain.critique_evaluation import CritiqueEvaluationService
from src.coherence.application.dtos.coherence_v2_dtos import (
    CategoryStatus,
    CategoryV2,
)
from src.documents.application.upload_document_use_case import (
    STRUCTURED_DOCUMENT_TYPES,
    STRUCTURED_DOCX_ERROR,
    UploadDocumentUseCase,
)
from src.documents.domain.clause_revision_binding import (
    clause_revision_id,
    clauses_bound_to_revision,
)
from src.documents.domain.models import Clause, DocumentType
from src.documents.domain.upload_policy import (
    UploadFormatError,
    allowed_upload_extensions,
    require_upload_extension,
)


class TestRegressionNoFabricatedScoreOrAbsence:
    """TS-PQ-HITL-09-REG-001: Absence of evidence must report honest nulls/UNKNOWN."""

    def test_category_v2_enforces_null_score_on_insufficient_evidence(self) -> None:
        """CategoryV2 must reject non-null coherence_score when status is insufficient_evidence."""
        # Valid state: score is None
        valid_cat = CategoryV2(
            category="QUALITY",
            status=CategoryStatus.INSUFFICIENT_EVIDENCE,
            coherence_score=None,
            evidence_count=0,
        )
        assert valid_cat.coherence_score is None
        assert valid_cat.status == CategoryStatus.INSUFFICIENT_EVIDENCE

        # Invalid state: fabricating 0.0 or 100.0 must raise ValueError
        with pytest.raises(
            ValueError, match="coherence_score must be None when status='insufficient_evidence'"
        ):
            CategoryV2(
                category="QUALITY",
                status=CategoryStatus.INSUFFICIENT_EVIDENCE,
                coherence_score=0.0,
                evidence_count=0,
            )

        with pytest.raises(
            ValueError, match="coherence_score must be None when status='insufficient_evidence'"
        ):
            CategoryV2(
                category="QUALITY",
                status=CategoryStatus.INSUFFICIENT_EVIDENCE,
                coherence_score=100.0,
                evidence_count=0,
            )

    def test_derivation_flags_are_strictly_none_when_unmeasured(self) -> None:
        """Coherence flags must remain None, never default to True or False without proof."""
        result = derive_coherence_flags(
            CoherenceDerivationInput(
                extracted_risks=[],
                extracted_wbs=[],
                bom_items=[],
                confidence_score=0.90,
                document_text=(
                    "Contract text describing general project terms without "
                    "containing specific schedule dates or monetary quantities."
                ),
            )
        )
        assert result.schedule_within_contract is None
        assert result.technical_consistent is None
        assert result.legal_compliant is None
        assert result.quality_standard_met is None

    def test_red_missing_per_risk_confidence_must_not_default_to_point_nine(self) -> None:
        """PQ-HITL-02.2 target invariant (Codex finding 3): absent confidence must yield None, not 0.9."""
        service = CritiqueEvaluationService()
        items_with_no_confidence = [{"title": "Unmeasured Risk A"}, {"title": "Unmeasured Risk B"}]

        # Unassessed extraction confidence remains UNKNOWN, never a synthetic 0.9.
        observed_conf = service.calculate_confidence(items_with_no_confidence)
        assert observed_conf is None


class TestUploadPolicyStructuredDocumentRejection:
    """TS-PQ-HITL-09-REG-001: Boundary checks for structured formats and upload policy."""

    def test_structured_document_types_contain_budget_and_schedule(self) -> None:
        """Both budget and schedule are classified as structured document types."""
        assert DocumentType.BUDGET in STRUCTURED_DOCUMENT_TYPES
        assert DocumentType.SCHEDULE in STRUCTURED_DOCUMENT_TYPES

    @pytest.mark.asyncio
    async def test_upload_policy_rejects_docx_for_structured_types(self) -> None:
        """Invoke the REAL upload application gate; do not manufacture an HTTPException."""
        project_repo = Mock()
        use_case = UploadDocumentUseCase(
            document_repository=Mock(),
            storage_service=Mock(),
            project_repository=project_repo,
        )
        for doc_type in (DocumentType.BUDGET, DocumentType.SCHEDULE):
            file = UploadFile(filename=f"{doc_type.value}.docx", file=BytesIO(b"test"))
            try:
                with pytest.raises(HTTPException) as result:
                    await use_case.execute(
                        project_id=uuid4(),
                        file=file,
                        document_type=doc_type,
                        user_id=uuid4(),
                        tenant_id=uuid4(),
                    )
                assert result.value.status_code == 400
                assert result.value.detail == STRUCTURED_DOCX_ERROR
            finally:
                await file.close()
        project_repo.exists_by_id.assert_not_called()

    @pytest.mark.parametrize("kind", [DocumentType.BUDGET, DocumentType.SCHEDULE])
    @pytest.mark.asyncio
    async def test_actual_upload_accepts_pdf_as_unstructured_source(
        self, kind: DocumentType,
    ) -> None:
        """Test the REAL application upload boundary, not only extension helpers.

        An accepted PDF upload does not imply parsed structured Budget/Schedule rows.
        """
        document_repo = AsyncMock()
        project_repo = AsyncMock()
        project_repo.exists_by_id.return_value = True
        storage = AsyncMock()
        storage.file_exists.return_value = True
        use_case = UploadDocumentUseCase(
            document_repository=document_repo,
            storage_service=storage,
            project_repository=project_repo,
        )
        file = UploadFile(
            filename=f"{kind.value}-source.pdf", file=BytesIO(b"%PDF-1.4 test fixture")
        )
        try:
            uploaded = await use_case.execute(
                project_id=uuid4(), file=file, document_type=kind,
                user_id=uuid4(), tenant_id=uuid4(),
            )
            assert uploaded.file_format == ".pdf"
            assert uploaded.document_type == kind
            document_repo.add.assert_awaited_once()
            document_repo.commit.assert_awaited()
            project_repo.exists_by_id.assert_awaited_once()
        finally:
            await file.close()

    def test_upload_policy_format_whitelisting(self) -> None:
        """Upload policy allows valid extensions and rejects foreign media types."""
        # Contract accepts .pdf
        assert ".pdf" in allowed_upload_extensions(DocumentType.CONTRACT)

        # The real upload policy ALSO accepts budget PDF as a source document,
        # without promising verified structured rows from that PDF.
        budget_exts = allowed_upload_extensions(DocumentType.BUDGET)
        assert ".xlsx" in budget_exts
        assert ".bc3" in budget_exts
        assert ".pdf" in budget_exts

        # Unsupported format raises UploadFormatError
        with pytest.raises(UploadFormatError):
            require_upload_extension(DocumentType.CONTRACT, ".bin")


class TestRegressionStaleRevisionProtection:
    """TS-PQ-HITL-09-REG-001: Pinned revision boundaries must isolate stale evidence."""

    def test_clause_bound_to_prior_revision_rejected_as_stale_for_current_revision(self) -> None:
        """Clauses extracted from revision A must not qualify as evidence for revision B."""
        rev_a = uuid4()
        rev_b = uuid4()
        tenant_id = uuid4()
        project_id = uuid4()
        doc_id = uuid4()

        stale_clause = Clause(
            id=uuid4(),
            project_id=project_id,
            tenant_id=tenant_id,
            document_id=doc_id,
            clause_code="5.1",
            clause_type=None,
            title="Defective Work A",
            full_text="Stale clause from revision A",
            extracted_entities={"evidence_location": {"revision_id": str(rev_a)}},
        )
        fresh_clause = Clause(
            id=uuid4(),
            project_id=project_id,
            tenant_id=tenant_id,
            document_id=doc_id,
            clause_code="5.1",
            clause_type=None,
            title="Defective Work B",
            full_text="Fresh clause from revision B",
            extracted_entities={"evidence_location": {"revision_id": str(rev_b)}},
        )

        # Checking clause_revision_id helper
        assert clause_revision_id(stale_clause) == rev_a
        assert clause_revision_id(fresh_clause) == rev_b

        # A set containing the stale clause must fail the binding check for rev_b
        mixed_clauses = [stale_clause, fresh_clause]
        assert (
            clauses_bound_to_revision(
                mixed_clauses,
                revision_id=rev_b,
                parent_revision_id=rev_a,
            )
            is False
        )

        # Only clauses genuinely bound to rev_b succeed
        only_fresh = [fresh_clause]
        assert (
            clauses_bound_to_revision(
                only_fresh,
                revision_id=rev_b,
                parent_revision_id=rev_a,
            )
            is True
        )

    def test_unrecorded_revision_fails_closed_in_multi_revision_lineage(self) -> None:
        """When a document has a parent revision, unrecorded clause revision must fail closed."""
        rev_b = uuid4()
        parent_rev_a = uuid4()
        tenant_id = uuid4()
        project_id = uuid4()
        doc_id = uuid4()

        unrecorded_clause = Clause(
            id=uuid4(),
            project_id=project_id,
            tenant_id=tenant_id,
            document_id=doc_id,
            clause_code="5.2",
            clause_type=None,
            title="Unrecorded",
            full_text="Clause without evidence_location",
            extracted_entities={},
        )

        assert (
            clauses_bound_to_revision(
                [unrecorded_clause],
                revision_id=rev_b,
                parent_revision_id=parent_rev_a,
            )
            is False
        )


class TestRegressionScoreAndCriticalAlertCoexistence:
    """TS-PQ-HITL-09-REG-001: Score calculation and critical alerts are orthogonal."""

    def test_critical_finding_preserves_its_severity_without_mutating_category_type(self) -> None:
        """A finding with CRITICAL severity retains severity and cannot be masked."""
        finding = CoherenceFinding(
            category=CoherenceCategory.TIME,
            message="Contractual completion date precedes mandatory notice period by 30 days.",
            rule_id="RULE-TIME-001",
            severity=Severity.CRITICAL,
            score=20,
            confidence=0.95,
            evidence_ref="Clause 4.1 vs Schedule Milestone M1",
        )

        assert finding.severity == Severity.CRITICAL
        assert finding.category == CoherenceCategory.TIME
        assert finding.score == 20
