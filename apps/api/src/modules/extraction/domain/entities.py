"""
C2Pro - Extraction Domain Entities

Defines the canonical data contract for extracted clauses.

Increment I3: Clause Extraction + Normalization
- ExtractedClause: Normalized clause DTO with validation
"""

from pydantic import BaseModel, Field, field_validator
from uuid import UUID
from typing import Optional
from datetime import date


class ExtractedClause(BaseModel):
    """
    Canonical DTO for a normalized clause extracted from a document.

    Refers to I3.3: Contract test - normalized clause schema.

    This DTO ensures that extracted clauses are properly structured and validated
    with complete provenance metadata for audit trails and human-in-the-loop routing.

    Attributes:
        clause_id: Unique identifier for the extracted clause
        document_id: ID of the document this clause belongs to
        version_id: ID of the document version this clause belongs to
        chunk_id: ID of the ingestion chunk this clause was extracted from
        text: The full text of the extracted clause
        type: Categorization of the clause (e.g., 'Payment Obligation', 'Delivery Term')
        modality: Modal verb or phrase indicating obligation level (e.g., 'Shall', 'May', 'Must Not')
        due_date: Specific date if the clause has a temporal constraint (ISO format)
        penalty_linkage: Description of linked penalties or consequences
        confidence: Confidence score (0.0-1.0) of the extraction accuracy
        ambiguity_flag: True if the clause's interpretation is ambiguous or uncertain
        actors: List of parties/actors involved in the clause (e.g., 'Contractor', 'Client')
        metadata: Additional arbitrary metadata for the clause (e.g., section, importance, review flags)
    """

    clause_id: UUID = Field(
        ...,
        description="Unique identifier for the extracted clause."
    )

    document_id: UUID = Field(
        ...,
        description="ID of the document this clause belongs to."
    )

    version_id: UUID = Field(
        ...,
        description="ID of the document version this clause belongs to."
    )

    chunk_id: UUID = Field(
        ...,
        description="ID of the ingestion chunk this clause was extracted from."
    )

    text: str = Field(
        ...,
        min_length=1,
        description="The full text of the extracted clause."
    )

    type: str = Field(
        ...,
        description="Categorization of the clause (e.g., 'Payment Obligation', 'Delivery Term')."
    )

    modality: str = Field(
        ...,
        description="Modal verb or phrase indicating obligation level (e.g., 'Shall', 'May', 'Must Not')."
    )

    due_date: Optional[date] = Field(
        None,
        description="Specific date if the clause has a temporal constraint."
    )

    penalty_linkage: Optional[str] = Field(
        None,
        description="Description of linked penalties or consequences."
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0-1.0) of the extraction accuracy."
    )

    ambiguity_flag: bool = Field(
        ...,
        description="True if the clause's interpretation is ambiguous or uncertain."
    )

    actors: list[str] = Field(
        default_factory=list,
        description="List of parties/actors involved in the clause (e.g., 'Contractor', 'Client')."
    )

    metadata: dict = Field(
        default_factory=dict,
        description="Additional arbitrary metadata for the clause (e.g., section, importance, review flags)."
    )

    @field_validator("confidence")
    @classmethod
    def validate_confidence_range(cls, v: float) -> float:
        """Validate that confidence is between 0.0 and 1.0."""
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {v}")
        return v

    @field_validator("due_date", mode="before")
    @classmethod
    def validate_due_date_format(cls, v):
        """
        Validate and convert due_date to proper date object.

        Accepts:
        - None
        - date object
        - ISO format string (YYYY-MM-DD)

        Rejects:
        - Invalid formats like YYYY/MM/DD
        - Invalid date strings
        """
        if v is None:
            return None

        if isinstance(v, date):
            return v

        if isinstance(v, str):
            # Try to parse ISO format
            try:
                return date.fromisoformat(v)
            except ValueError:
                raise ValueError(
                    f"Invalid date format: {v}. Expected ISO format (YYYY-MM-DD) or date object."
                )

        raise ValueError(
            f"Invalid due_date type: {type(v)}. Expected date object or ISO format string."
        )

    @field_validator("ambiguity_flag", mode="before")
    @classmethod
    def validate_ambiguity_flag_type(cls, v):
        """Validate that ambiguity_flag is a boolean."""
        if not isinstance(v, bool):
            raise ValueError(
                f"ambiguity_flag must be a boolean, got {type(v).__name__}"
            )
        return v

    model_config = {
        "frozen": False,
        "str_strip_whitespace": True,
        "validate_assignment": True,
    }
