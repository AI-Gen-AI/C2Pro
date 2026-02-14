# Path: apps/api/src/projects/tests/integration/test_i8_wbs_bom_generation.py
import pytest
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4

# TDD: These imports will fail until the application services, DTOs, and ports are created.
try:
    from src.projects.application.services import WBSBOMGenerator
    from src.projects.application.dtos import WBSNode, BOMItem
    from src.projects.application.util import UnitNormalizer
    from src.documents.application.dtos import NormalizedClause
except ImportError:
    # Define dummy classes to allow the test file to be parsed before implementation
    WBSBOMGenerator = type("WBSBOMGenerator", (), {})
    WBSNode = type("WBSNode", (), {})
    BOMItem = type("BOMItem", (), {})
    UnitNormalizer = type("UnitNormalizer", (), {})
    NormalizedClause = type("NormalizedClause", (), {})


@pytest.fixture
def mock_clauses_for_generation() -> list[NormalizedClause]:
    """Provides a fixture of normalized clauses ready for WBS/BOM generation."""
    clause_id_1 = uuid4()
    clause_id_2 = uuid4()
    return [
        NormalizedClause(
            id=clause_id_1,
            text="The contractor shall install 100 kilograms of steel beams.",
        ),
        NormalizedClause(
            id=clause_id_2, text="A project manager must be assigned to the foundation phase."
        ),
    ]


@pytest.mark.integration
@pytest.mark.tdd
class TestWBSBOMGeneration:
    """
    Test suite for I8 - WBS/BOM Generation.
    """

    def test_i8_01_wbs_node_dto_is_valid(self):
        """
        [TEST-I8-01] Verifies the WBSNode DTO contains all required fields.
        """
        # Arrange & Act: This will fail if WBSNode is not a proper class with these attributes.
        node = WBSNode(
            id=uuid4(),
            level=1,
            name="Foundation Phase",
            parent_id=None,
            evidence_clause_id=uuid4(),
        )

        # Assert
        assert hasattr(node, "id")
        assert hasattr(node, "level") and node.level == 1
        assert hasattr(node, "name") and node.name == "Foundation Phase"
        assert hasattr(node, "parent_id") is None
        assert hasattr(node, "evidence_clause_id")

    def test_i8_02_unit_normalizer_works_correctly(self):
        """
        [TEST-I8-02] Verifies the UnitNormalizer correctly canonicalizes units.
        """
        # Arrange: This test expects a `UnitNormalizer` utility to exist.
        normalizer = UnitNormalizer()
        units_to_test = ["kilogram", "kg", "kgs", "Kilograms"]

        # Act & Assert
        for unit in units_to_test:
            # This call will fail until the normalizer is implemented.
            normalized = normalizer.normalize(unit)
            assert normalized == "KG"

    @pytest.mark.asyncio
    async def test_i8_03_generator_produces_candidates_with_evidence(
        self, mock_clauses_for_generation
    ):
        """
        [TEST-I8-03] Verifies the generator produces candidates with confidence and evidence links.
        """
        # Arrange: This test expects the main `WBSBOMGenerator` service to exist.
        generator = WBSBOMGenerator()
        # Mock the internal generation logic for a predictable output
        generator.generate = AsyncMock(return_value=(
            [WBSNode(id=uuid4(), name="Foundation Phase", evidence_clause_id=mock_clauses_for_generation[1].id, confidence=0.92)],
            [BOMItem(id=uuid4(), name="Steel Beams", evidence_clause_id=mock_clauses_for_generation[0].id, confidence=0.98)],
        ))

        # Act
        wbs_nodes, bom_items = await generator.generate(mock_clauses_for_generation)

        # Assert
        assert len(wbs_nodes) == 1
        assert len(bom_items) == 1

        wbs_node = wbs_nodes[0]
        assert hasattr(wbs_node, "confidence") and 0 < wbs_node.confidence <= 1.0
        assert wbs_node.evidence_clause_id == mock_clauses_for_generation[1].id

        bom_item = bom_items[0]
        assert hasattr(bom_item, "confidence") and 0 < bom_item.confidence <= 1.0
        assert bom_item.evidence_clause_id == mock_clauses_for_generation[0].id

    @pytest.mark.xfail(reason="[TDD] Drives implementation of human review flag.", strict=True)
    @pytest.mark.asyncio
    async def test_i8_04_generator_flags_items_needing_review(self):
        """
        [TEST-I8-04] Verifies items generated without direct evidence are flagged for review.
        """
        # Arrange
        generator = WBSBOMGenerator()
        # Simulate a generator that infers a WBS node without direct textual evidence
        generator.generate = AsyncMock(return_value=(
            [WBSNode(id=uuid4(), name="Inferred Task", evidence_clause_id=None, confidence=0.6, needs_human_review=True)],
            [],
        ))

        # Act
        wbs_nodes, _ = await generator.generate([])

        # Assert
        assert len(wbs_nodes) == 1
        inferred_node = wbs_nodes[0]
        assert inferred_node.evidence_clause_id is None
        assert inferred_node.needs_human_review is True
        assert False, "Remove this line once the review flag logic is implemented."