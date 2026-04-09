"""
Coherence Scoring Derivation Service.

Pure domain logic for deriving coherence flags from extracted analysis data.
Refers to TASK-REV-007.
Refers to Suite ID: TS-ARCH-003.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CoherenceDerivationInput:
    """Input data for coherence derivation."""
    extracted_risks: list[dict[str, Any]]
    extracted_wbs: list[dict[str, Any]]
    bom_items: list[dict[str, Any]]
    confidence_score: float
    document_text: str


@dataclass
class CoherenceDerivationResult:
    """Result of coherence derivation."""
    scope_defined: bool
    schedule_within_contract: bool
    technical_consistent: bool
    legal_compliant: bool
    quality_standard_met: bool
    bom_items: list[dict[str, Any]]
    contract_price: float
    has_budget_risks: bool
    poor_extraction_quality: bool
    avg_wbs_confidence: float
    risk_count: int
    wbs_count: int
    quality_note: str

    def to_calculation_inputs(self) -> dict[str, Any]:
        """Return coherence calculation kwargs derived from domain rules."""
        return {
            "contract_price": self.contract_price,
            "bom_items": self.bom_items,
            "scope_defined": self.scope_defined,
            "schedule_within_contract": self.schedule_within_contract,
            "technical_consistent": self.technical_consistent,
            "legal_compliant": self.legal_compliant,
            "quality_standard_met": self.quality_standard_met,
            "document_count": 1,
        }


class CoherenceScoringDerivationService:
    """
    Derives coherence flags from extracted analysis data.

    Pure domain service - no external dependencies.
    """

    MIN_CONFIDENCE_THRESHOLD = 0.5
    MIN_DOCUMENT_LENGTH = 100
    MIN_WBS_CONFIDENCE = 0.5

    RISK_CATEGORIES = {
        "SCOPE": {"SCOPE"},
        "BUDGET": {"BUDGET", "FINANCIAL"},
        "SCHEDULE": {"SCHEDULE", "TIME"},
        "TECHNICAL": {"TECHNICAL"},
        "LEGAL": {"LEGAL"},
        "QUALITY": {"QUALITY"},
    }

    def derive(self, input_data: CoherenceDerivationInput) -> CoherenceDerivationResult:
        """
        Derive coherence flags from input data.

        Args:
            input_data: Extracted analysis data

        Returns:
            Derived coherence flags
        """
        confidence = input_data.confidence_score
        doc_text = input_data.document_text
        wbs = input_data.extracted_wbs
        risks = input_data.extracted_risks
        bom = input_data.bom_items

        low_confidence = confidence < self.MIN_CONFIDENCE_THRESHOLD
        short_document = len(doc_text.strip()) < self.MIN_DOCUMENT_LENGTH

        avg_wbs_conf = self._calculate_avg_wbs_confidence(wbs)

        poor_extraction_quality = (
            low_confidence
            or short_document
            or (len(wbs) > 0 and avg_wbs_conf < self.MIN_WBS_CONFIDENCE)
        )

        scope_defined = self._derive_scope_defined(
            risks=risks,
            wbs=wbs,
            poor_quality=poor_extraction_quality,
        )

        has_budget_risks = self._has_high_risk_in_categories(risks, self.RISK_CATEGORIES["BUDGET"])
        bom_items = self._mark_bom_unassigned_if_needed(bom, has_budget_risks)

        schedule_within_contract = not self._has_high_risk_in_categories(
            risks, self.RISK_CATEGORIES["SCHEDULE"]
        )
        technical_consistent = not self._has_high_risk_in_categories(
            risks, self.RISK_CATEGORIES["TECHNICAL"]
        )
        legal_compliant = not self._has_high_risk_in_categories(
            risks, self.RISK_CATEGORIES["LEGAL"]
        )
        quality_standard_met = not self._has_high_risk_in_categories(
            risks, self.RISK_CATEGORIES["QUALITY"]
        )

        contract_price = self._calculate_contract_price(bom_items)

        quality_note = ""
        if poor_extraction_quality:
            quality_note = f", LOW QUALITY (conf={confidence:.2f})"

        return CoherenceDerivationResult(
            scope_defined=scope_defined,
            schedule_within_contract=schedule_within_contract,
            technical_consistent=technical_consistent,
            legal_compliant=legal_compliant,
            quality_standard_met=quality_standard_met,
            bom_items=bom_items,
            contract_price=contract_price,
            has_budget_risks=has_budget_risks,
            poor_extraction_quality=poor_extraction_quality,
            avg_wbs_confidence=avg_wbs_conf,
            risk_count=len(risks),
            wbs_count=len(wbs),
            quality_note=quality_note,
        )

    def _calculate_avg_wbs_confidence(self, wbs: list[dict[str, Any]]) -> float:
        """Calculate average confidence of WBS items."""
        confidences = [
            item.get("confidence", 0.0)
            for item in wbs
            if isinstance(item.get("confidence"), (int, float))
        ]
        return sum(confidences) / len(confidences) if confidences else 0.0

    def _has_high_risk_in_categories(self, risks: list[dict], categories: set[str]) -> bool:
        """Check if any risk has HIGH/CRITICAL impact in given categories."""
        for risk in risks:
            cat = (risk.get("category") or "").upper()
            impact = (risk.get("impact") or "").upper()
            if cat in categories and impact in ("HIGH", "CRITICAL"):
                return True
        return False

    def _derive_scope_defined(
        self,
        risks: list[dict],
        wbs: list[dict],
        poor_quality: bool,
    ) -> bool:
        """Derive whether scope is properly defined."""
        has_scope_risks = self._has_high_risk_in_categories(risks, self.RISK_CATEGORIES["SCOPE"])
        has_meaningful_content = len(wbs) > 0 or len(risks) > 0
        return has_meaningful_content and not has_scope_risks and not poor_quality

    def _mark_bom_unassigned_if_needed(
        self,
        bom: list[dict],
        has_budget_risks: bool,
    ) -> list[dict]:
        """Mark BOM items as unassigned if budget risks exist."""
        if has_budget_risks and bom:
            return [
                {**item, "budget_line_assigned": False}
                for item in bom
            ]
        return list(bom)

    def _calculate_contract_price(self, bom: list[dict]) -> float:
        """Calculate total contract price from BOM items."""
        return sum(
            float(item.get("amount", 0) or item.get("total", 0) or 0)
            for item in bom
        )


def derive_coherence_flags(input_data: CoherenceDerivationInput) -> CoherenceDerivationResult:
    """
    Convenience function for coherence flag derivation.

    Args:
        input_data: Extracted analysis data

    Returns:
        Derived coherence flags
    """
    service = CoherenceScoringDerivationService()
    return service.derive(input_data)
