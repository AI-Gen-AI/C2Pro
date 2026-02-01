
import abc
import re
from uuid import UUID, uuid4
from typing import List, Optional, Any
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

# --- Constants ---
MAX_CONTENT_LENGTH = 5000
EMBEDDING_DIMENSION = 1536

# --- Ports ---
class EmbeddingService(abc.ABC):
    """
    Port for an external service that can generate text embeddings.
    """
    @abc.abstractmethod
    def generate_embedding(self, text: str) -> List[float]:
        """Generates an embedding vector for the given text."""
        raise NotImplementedError

# --- Domain Entity ---
class Clause(BaseModel):
    """
    Represents a clause within a document. This is a domain entity.
    It is immutable by design. Any 'update' returns a new instance.
    """
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    document_id: UUID
    content: str
    clause_number: Optional[str] = None
    clause_text_embedding: Optional[List[float]] = None

    @field_validator('content')
    @classmethod
    def validate_content(cls, value: str) -> str:
        if not value:
            raise ValueError("Clause content cannot be empty")
        if len(value) > MAX_CONTENT_LENGTH:
            raise ValueError("Clause content exceeds maximum length")
        return value

    @field_validator('clause_number')
    @classmethod
    def normalize_clause_number(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        
        normalized_value = value.strip().rstrip('.').lower()
        
        # Dictionary for Spanish numerals to numbers
        word_map = {
            "primera": "1", "segunda": "2", "tercera": "3", "cuarta": "4", 
            "quinta": "5", "sexta": "6", "septima": "7", "octava": "8", 
            "novena": "9", "decima": "10"
        }
        
        if normalized_value in word_map:
            return word_map[normalized_value]
        
        # Check if it's a valid numeric/decimal format
        if re.match(r'^\d+(\.\d+)*$', normalized_value):
            return normalized_value

        raise ValueError("Invalid clause number format")

    @field_validator('clause_text_embedding')
    @classmethod
    def validate_embedding_dimension(cls, value: Optional[List[float]]) -> Optional[List[float]]:
        if value is not None and len(value) != EMBEDDING_DIMENSION:
            raise ValueError(f"Embedding must have {EMBEDDING_DIMENSION} dimensions")
        return value

    def update_embedding(self, embedding_service: EmbeddingService) -> 'Clause':
        """
        Generates an embedding for the clause's content and returns a new Clause instance.
        
        Args:
            embedding_service: The service to use for generating the embedding vector.

        Returns:
            A new, immutable Clause instance with the updated embedding.
        """
        if not self.content:
            raise ValueError("Cannot generate embedding for empty content")

        new_embedding = embedding_service.generate_embedding(self.content)
        
        # Since the model is frozen, we use model_copy to create a new instance
        return self.model_copy(update={"clause_text_embedding": new_embedding})
