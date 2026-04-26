"""
Tests for unknown coherence dimensions when extraction evidence is absent.

Refers to Suite ID: TS-UD-ANA-GRP-001.
Refers to backlog_id: TASK-COH-V1-02.
"""

from src.analysis.domain.coherence_derivation import (
    CoherenceDerivationInput,
    derive_coherence_flags,
)


def test_dimension_flags_are_none_when_no_extractions_exist() -> None:
    """TS-UD-ANA-GRP-001: No dimension evidence must not default to pass."""
    result = derive_coherence_flags(
        CoherenceDerivationInput(
            extracted_risks=[],
            extracted_wbs=[],
            bom_items=[],
            confidence_score=0.95,
            document_text=(
                "This contract text is intentionally long enough to pass the "
                "document quality threshold while lacking schedule and budget evidence."
            ),
        )
    )

    assert result.schedule_within_contract is None
    assert result.technical_consistent is None
    assert result.legal_compliant is None
    assert result.quality_standard_met is None
