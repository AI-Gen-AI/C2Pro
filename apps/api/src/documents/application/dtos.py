"""
Data Transfer Objects (DTOs) for the Documents application layer.

DTOs are simple data carriers used to transfer data between layers,
especially between the presentation (e.g., API) and application layers.
They help to decouple the core business logic from the specific details
of the API, making the system more modular and easier to test.
"""

from dataclasses import dataclass
from uuid import UUID
from src.documents.domain.models import DocumentType


@dataclass(frozen=True)
class CreateDocumentDTO:
    """DTO for creating a new document."""
    project_id: UUID
    filename: str
    document_type: DocumentType
    # Optional fields
    file_format: str | None = None
    storage_url: str | None = None
    file_size_bytes: int | None = None
    created_by: UUID | None = None
    document_metadata: dict | None = None