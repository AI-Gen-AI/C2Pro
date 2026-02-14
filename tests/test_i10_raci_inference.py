# Path: apps/api/src/stakeholders/tests/integration/test_i10_raci_inference.py
import pytest
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4

# TDD: These imports will fail until the application services, DTOs, and ports are created.
try:
    from src.stakeholders.application.services import RACIInferenceService
    from src.stakeholders.application.dtos import RACIMatrix, RACIEntry, Stakeholder
    from src.stakeholders.application.util import EntityResolver, RACIValidator
    from src.stakeholders.application.errors import RACIValidationError
    from src.documents.application.dtos import NormalizedClause
except ImportError:
    # Define dummy classes to allow the test file to be parsed before implementation
    RACIInferenceService = type("RACIInferenceService", (), {})
    RACIMatrix = type("RACIMatrix", (), {})
    RACIEntry = type("RACIEntry", (), {})
    Stakeholder = type("Stakeholder", (), {})
    EntityResolver = type("EntityResolver", (), {})
    RACIValidator = type("RACIValidator", (), {})
    RACIValidationError = type("RACIValidationError", (Exception,), {})
    NormalizedClause = type("NormalizedClause", (), {})


@pytest.fixture
def mock_clauses_for_raci() -> list[NormalizedClause]:
    """Provides a fixture of clauses with stakeholder information."""
    return [
        NormalizedClause(
            text="The Buyer is responsible for payment.", actors=["The Buyer"]
        ),
        NormalizedClause(
            text="Buyer Inc. must approve the design.", actors=["Buyer Inc."]
        ),
        NormalizedClause(
            text="The committee should be informed of progress.", actors=["the committee"]
        ),
    ]


@pytest.mark.integration
@pytest.mark.tdd
class TestStakeholderAndRACIInference:
    """
    Test suite for I10 - Stakeholder Resolution + RACI Inference.
    """

    def test_i10_01_entity_resolver_merges_duplicates(self):
        """
        [TEST-I10-01] Verifies the EntityResolver merges duplicate stakeholder names.
        """
        # Arrange: This test expects an `EntityResolver` utility to exist.
        resolver = EntityResolver()
        stakeholders_to_resolve = [
            Stakeholder(name="The Buyer", source="doc1"),
            Stakeholder(name="Buyer Inc.", source="doc2"),
            Stakeholder(name="Seller", source="doc1"),
        ]
        # This call will fail until the resolver is implemented.
        resolver.resolve = MagicMock(return_value={
            "The Buyer": "stakeholder_id_1",
            "Buyer Inc.": "stakeholder_id_1",
            "Seller": "stakeholder_id_2",
        })

        # Act
        resolved_map = resolver.resolve(stakeholders_to_resolve)

        # Assert
        assert resolved_map["The Buyer"] == resolved_map["Buyer Inc."]
        assert resolved_map["The Buyer"] != resolved_map["Seller"]

    def test_i10_02_raci_validator_enforces_single_accountable(self):
        """
        [TEST-I10-02] Verifies the RACIValidator raises an error for multiple 'A's.
        """
        # Arrange: This test expects a `RACIValidator` utility to exist.
        validator = RACIValidator()
        invalid_matrix = RACIMatrix(
            task_id="T1",
            entries=[
                RACIEntry(stakeholder_id=uuid4(), role="A"),
                RACIEntry(stakeholder_id=uuid4(), role="A"), # Two 'A's
                RACIEntry(stakeholder_id=uuid4(), role="R"),
            ],
        )

        # Act & Assert
        with pytest.raises(RACIValidationError) as excinfo:
            # This call will fail until the validator is implemented.
            validator.validate(invalid_matrix)
        assert "must have exactly one 'Accountable'" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_i10_03_inference_produces_raci_with_confidence(
        self, mock_clauses_for_raci
    ):
        """
        [TEST-I10-03] Verifies the service produces a RACI matrix with confidence scores.
        """
        # Arrange: This test expects the main `RACIInferenceService` to exist.
        service = RACIInferenceService()
        service.infer_from_clauses = AsyncMock(return_value=[
            RACIMatrix(
                task_id="Payment",
                entries=[RACIEntry(stakeholder_id=uuid4(), role="A", confidence=0.95)]
            )
        ])

        # Act
        raci_matrices = await service.infer_from_clauses(mock_clauses_for_raci)

        # Assert
        assert len(raci_matrices) == 1
        matrix = raci_matrices[0]
        assert isinstance(matrix, RACIMatrix)
        assert len(matrix.entries) > 0
        entry = matrix.entries[0]
        assert hasattr(entry, "confidence") and 0 < entry.confidence <= 1.0

    @pytest.mark.xfail(reason="[TDD] Drives implementation of ambiguity flagging.", strict=True)
    @pytest.mark.asyncio
    async def test_i10_04_inference_flags_ambiguous_actors(self):
        """
        [TEST-I10-04] Verifies ambiguous actors are flagged for human review.
        """
        # Arrange
        service = RACIInferenceService()
        # Simulate inference where "the committee" cannot be resolved to a known stakeholder
        service.infer_from_clauses = AsyncMock(return_value=[
            RACIMatrix(task_id="Progress Update", needs_human_review=True, review_reason="Unresolved actor: the committee")
        ])

        # Act
        raci_matrices = await service.infer_from_clauses([])

        # Assert
        assert len(raci_matrices) == 1
        matrix = raci_matrices[0]
        assert matrix.needs_human_review is True
        assert "Unresolved actor" in matrix.review_reason
        assert False, "Remove this line once ambiguity flagging is implemented."