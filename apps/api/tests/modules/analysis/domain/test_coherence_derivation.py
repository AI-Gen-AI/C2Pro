"""
TS-ARCH-003

Domain tests for coherence derivation service outputs.
"""

from __future__ import annotations

from src.analysis.domain.coherence_derivation import (
    CoherenceDerivationInput,
    CoherenceScoringDerivationService,
)


def test_derivation_exposes_calculation_inputs_for_coherence_service() -> None:
    """Derived flags and totals should be available as calculation inputs."""
    service = CoherenceScoringDerivationService()

    result = service.derive(
        CoherenceDerivationInput(
            extracted_risks=[{"category": "LEGAL", "impact": "HIGH"}],
            extracted_wbs=[{"code": "1.0", "confidence": 0.9}],
            bom_items=[{"amount": 1250.0, "budget_line_assigned": True}],
            confidence_score=0.9,
            document_text=(
                "This is a sufficiently long contract document used to validate "
                "coherence derivation calculation input mapping."
            ),
        )
    )

    assert result.to_calculation_inputs() == {
        "contract_price": 1250.0,
        "bom_items": [{"amount": 1250.0, "budget_line_assigned": True}],
        "scope_defined": True,
        "schedule_within_contract": None,
        "technical_consistent": None,
        "legal_compliant": False,
        "quality_standard_met": None,
        "document_count": 1,
    }


def test_derivation_tracks_budget_risk_without_private_service_access() -> None:
    """Budget-risk metadata should be part of the public derivation result."""
    service = CoherenceScoringDerivationService()

    result = service.derive(
        CoherenceDerivationInput(
            extracted_risks=[{"category": "FINANCIAL", "impact": "CRITICAL"}],
            extracted_wbs=[{"code": "1.0", "confidence": 0.95}],
            bom_items=[{"amount": 200.0, "budget_line_assigned": True}],
            confidence_score=0.95,
            document_text=(
                "This is a sufficiently long contract document used to validate "
                "budget risk derivation metadata."
            ),
        )
    )

    assert result.has_budget_risks is True
    assert result.risk_count == 1
    assert result.wbs_count == 1
