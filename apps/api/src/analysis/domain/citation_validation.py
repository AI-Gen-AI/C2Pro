"""
Citation Validation Service.

Pure domain logic for validating that extracted data can be traced back to source text.
Refers to TASK-REV-007.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Citation:
    """Represents a validated citation."""
    type: str
    item: str
    quote: str
    found_in_source: bool


@dataclass
class CitationValidationResult:
    """Result of citation validation."""
    citations: list[Citation]
    validation_passed: bool
    validated_count: int
    total_count: int


class CitationValidatorService:
    """
    Validates that extracted data can be traced back to source text.

    Pure domain service - no external dependencies.
    """

    VALIDATION_THRESHOLD = 0.6
    WBS_FRAGMENT_LENGTH = 80

    def validate(
        self,
        source_text: str,
        risks: list[dict[str, Any]],
        wbs_items: list[dict[str, Any]],
    ) -> CitationValidationResult:
        """
        Validate citations against source text.

        Args:
            source_text: Original document text
            risks: Extracted risks with source quotes
            wbs_items: Extracted WBS items with descriptions

        Returns:
            Validation result with citations and pass/fail status
        """
        text_lower = source_text.lower()
        citations: list[Citation] = []
        all_valid = True

        for risk in risks:
            citation = self._validate_risk_citation(risk, text_lower)
            citations.append(citation)
            if not citation.found_in_source and citation.quote:
                all_valid = False

        for wbs in wbs_items:
            citation = self._validate_wbs_citation(wbs, text_lower)
            citations.append(citation)

        validated_count = sum(1 for c in citations if c.found_in_source)
        total_count = len(citations)

        validation_passed = all_valid or (
            total_count > 0 and validated_count / total_count >= self.VALIDATION_THRESHOLD
        )

        return CitationValidationResult(
            citations=citations,
            validation_passed=validation_passed,
            validated_count=validated_count,
            total_count=total_count,
        )

    def _validate_risk_citation(
        self,
        risk: dict[str, Any],
        text_lower: str,
    ) -> Citation:
        """Validate a risk citation."""
        quote = risk.get("source_quote") or risk.get("source_text_snippet") or ""
        found = bool(quote and quote.lower() in text_lower)
        return Citation(
            type="risk",
            item=risk.get("title") or risk.get("summary", ""),
            quote=quote,
            found_in_source=found,
        )

    def _validate_wbs_citation(
        self,
        wbs: dict[str, Any],
        text_lower: str,
    ) -> Citation:
        """Validate a WBS item citation."""
        desc = wbs.get("description") or wbs.get("name") or ""
        fragment = desc[: self.WBS_FRAGMENT_LENGTH].lower() if desc else ""
        found = bool(fragment and fragment in text_lower)
        return Citation(
            type="wbs",
            item=wbs.get("code", ""),
            quote=desc[:120] if desc else "",
            found_in_source=found,
        )


def validate_citations(
    source_text: str,
    risks: list[dict[str, Any]],
    wbs_items: list[dict[str, Any]],
) -> CitationValidationResult:
    """
    Convenience function for citation validation.

    Args:
        source_text: Original document text
        risks: Extracted risks
        wbs_items: Extracted WBS items

    Returns:
        Validation result
    """
    validator = CitationValidatorService()
    return validator.validate(source_text, risks, wbs_items)
