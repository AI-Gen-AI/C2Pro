"""
I3 - Clause Extraction Domain Tests

Tests for ExtractedClause entity validation and contract tests.
Refers to I3.3: Contract test - normalized clause schema.
"""

import pytest
from uuid import uuid4
from datetime import date
from pydantic import ValidationError

from src.modules.extraction.domain.entities import ExtractedClause


def test_i3_normalized_clause_schema_contract():
    """Refers to I3.3: Contract test - normalized clause schema (type, modality, due date, penalty linkage)."""
    clause = ExtractedClause(
        clause_id=uuid4(),
        document_id=uuid4(),
        version_id=uuid4(),
        chunk_id=uuid4(),
        text="The Contractor shall deliver materials by 2024-12-31, subject to penalties as per Section 7.",
        type="Delivery Obligation",
        modality="Shall",
        due_date=date(2024, 12, 31),
        penalty_linkage="Late delivery penalty applies as per Section 7.",
        confidence=0.98,
        ambiguity_flag=False,
        actors=["Contractor", "Client"],
        metadata={"section": "7"}
    )

    assert clause.clause_id is not None
    assert clause.text == "The Contractor shall deliver materials by 2024-12-31, subject to penalties as per Section 7."
    assert clause.type == "Delivery Obligation"
    assert clause.modality == "Shall"
    assert clause.due_date == date(2024, 12, 31)
    assert clause.penalty_linkage == "Late delivery penalty applies as per Section 7."
    assert clause.confidence == 0.98
    assert clause.ambiguity_flag is False
    assert "Contractor" in clause.actors
    assert "Client" in clause.actors


def test_i3_normalized_clause_schema_fails_on_invalid_data():
    """Refers to I3.3: Contract test - normalized clause schema fails on invalid data."""
    with pytest.raises(ValidationError):
        ExtractedClause(
            clause_id=uuid4(),
            document_id=uuid4(),
            version_id=uuid4(),
            chunk_id=uuid4(),
            text="Invalid clause data.",
            type="Invalid Type",
            modality="Invalid Modality",
            due_date="2024/12/31",  # Incorrect date format
            penalty_linkage=None,
            confidence=1.1,  # Out of range
            ambiguity_flag="not_a_bool",  # Incorrect type
            actors=[],
            metadata={}
        )
