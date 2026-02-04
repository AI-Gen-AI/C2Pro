"""
TS-UD-DOC-CLS-001: Clause entity tests.
"""

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from src.documents.domain.clause_entity import Clause, EmbeddingService

# --- Test Data and Fixtures ---
@pytest.fixture
def minimal_clause_data():
    """Provides minimal valid data for Clause creation."""
    return {
        "tenant_id": uuid4(),
        "document_id": uuid4(),
        "content": "This is the content of the clause."
    }

@pytest.fixture
def full_clause_data(minimal_clause_data):
    """Provides a full set of valid data for Clause creation."""
    return {
        **minimal_clause_data,
        "id": uuid4(),
        "clause_number": "Primera",
        "clause_text_embedding": [0.1] * 1536  # Assuming a vector size of 1536
    }

# --- Test Cases ---
class TestClauseEntity:
    """Refers to Suite ID: TS-UD-DOC-CLS-001"""

    def test_001_clause_creation_with_all_fields(self, full_clause_data):
        """Tests successful creation of a Clause with all fields provided."""
        clause = Clause(**full_clause_data)
        assert clause.id == full_clause_data["id"]
        assert clause.tenant_id == full_clause_data["tenant_id"]
        assert clause.document_id == full_clause_data["document_id"]
        assert clause.content == full_clause_data["content"]
        assert clause.clause_number == "1" # Should be normalized
        assert len(clause.clause_text_embedding) == 1536

    def test_002_clause_creation_minimum_fields(self, minimal_clause_data):
        """Tests successful creation with only required fields."""
        clause = Clause(**minimal_clause_data)
        assert isinstance(clause.id, UUID) # Should be auto-generated
        assert clause.tenant_id == minimal_clause_data["tenant_id"]
        assert clause.document_id == minimal_clause_data["document_id"]
        assert clause.content == minimal_clause_data["content"]
        assert clause.clause_number is None
        assert clause.clause_text_embedding is None

    @pytest.mark.parametrize("missing_field", ["content", "document_id", "tenant_id"])
    def test_003_004_005_clause_creation_fails_without_required_fields(self, minimal_clause_data, missing_field):
        """Tests that creation fails if a required field is missing."""
        invalid_data = minimal_clause_data.copy()
        del invalid_data[missing_field]
        with pytest.raises(ValidationError, match=f"Field required"):
            Clause(**invalid_data)

    def test_006_clause_immutability_after_creation(self, minimal_clause_data):
        """Tests that a Clause instance is immutable after creation."""
        clause = Clause(**minimal_clause_data)
        with pytest.raises(ValidationError, match="Instance is frozen"):
            clause.content = "New content"
        with pytest.raises(ValidationError, match="Instance is frozen"):
            clause.id = uuid4()
    
    @pytest.mark.parametrize("input_num, expected_num", [
        ("Primera", "1"),
        ("Segunda", "2"),
        ("1.4.2", "1.4.2"),
        ("Tercera.", "3"),
        ("  Cuarta  ", "4"),
        ("DECIMA", "10")
    ])
    def test_007_008_009_010_clause_number_normalization(self, minimal_clause_data, input_num, expected_num):
        """Tests normalization of various clause number formats."""
        clause = Clause(**minimal_clause_data, clause_number=input_num)
        assert clause.clause_number == expected_num

    @pytest.mark.parametrize("invalid_num", ["Invalid", "Zero", "1.a.2"])
    def test_clause_number_invalid_format_rejected(self, minimal_clause_data, invalid_num):
        """Tests that invalid clause number formats are rejected."""
        with pytest.raises(ValidationError, match="Invalid clause number format"):
            Clause(**minimal_clause_data, clause_number=invalid_num)

    def test_011_clause_content_max_length(self, minimal_clause_data):
        """Tests that content exceeding the maximum length is rejected."""
        data = {**minimal_clause_data, "content": "a" * 5001}
        with pytest.raises(ValidationError, match="Clause content exceeds maximum length"):
            Clause(**data)

    def test_012_clause_content_empty_rejected(self, minimal_clause_data):
        """Tests that empty content is rejected."""
        data = {**minimal_clause_data, "content": ""}
        with pytest.raises(ValidationError, match="Clause content cannot be empty"):
            Clause(**data)

    @pytest.mark.parametrize("invalid_id", ["not-a-uuid", 12345, None])
    def test_014_016_fk_invalid_rejected(self, minimal_clause_data, invalid_id):
        """Tests that invalid UUIDs for foreign keys are rejected."""
        invalid_document_data = {**minimal_clause_data, "document_id": invalid_id}
        invalid_tenant_data = {**minimal_clause_data, "tenant_id": invalid_id}
        with pytest.raises(ValidationError):
            Clause(**invalid_document_data)
        with pytest.raises(ValidationError):
            Clause(**invalid_tenant_data)
    
    # Tests 017 and 018 are persistence layer concerns and not tested here.

    def test_019_clause_embedding_vector_size(self, minimal_clause_data):
        """Tests that an embedding vector of incorrect size is rejected."""
        with pytest.raises(ValidationError, match="Embedding must have 1536 dimensions"):
            Clause(**minimal_clause_data, clause_text_embedding=[0.1] * 10)
    
    def test_021_clause_embedding_null_allowed(self, minimal_clause_data):
        """Tests that the embedding can be null on creation."""
        clause = Clause(**minimal_clause_data, clause_text_embedding=None)
        assert clause.clause_text_embedding is None

    def test_020_022_clause_embedding_generation_and_update(self, minimal_clause_data):
        """Tests that generating an embedding returns a new, updated Clause instance."""
        class FakeEmbeddingService(EmbeddingService):
            def generate_embedding(self, text: str) -> list[float]:
                return [0.2] * 1536

        mock_service = FakeEmbeddingService()
        expected_vector = [0.2] * 1536

        # 2. Create an initial clause without an embedding
        initial_clause = Clause(**minimal_clause_data)
        assert initial_clause.clause_text_embedding is None

        # 3. Call the method to update the embedding
        updated_clause = initial_clause.update_embedding(mock_service)

        # 4. Assertions
        assert updated_clause is not initial_clause, "A new instance should be returned"
        assert updated_clause.clause_text_embedding == expected_vector
        assert updated_clause.id == initial_clause.id # All other fields should be identical
        assert updated_clause.content == initial_clause.content
        # The original instance should remain unchanged
        assert initial_clause.clause_text_embedding is None
