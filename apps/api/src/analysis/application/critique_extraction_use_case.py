"""
Application use case: run the LLM critique and evaluate its result.

Wraps `CritiqueExtractionService` (LLM call) + `CritiqueEvaluationService`
(pure domain math) behind a single predictable output consumed by the
LangGraph critique node and its outgoing conditional edge.

Refers to EPIC-CORE-DECOUPLE / TASK-IMPL-010 Phase 2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import re

# Deterministic checks are intentionally narrow. They identify demonstrable
# contradictions in source-backed contractual timeframes/obligation ownership;
# they do not attempt a legal review or declare all model claims verified.
def _source_consistency_issues(
    *, source_text: str | None, risks: list[dict[str, Any]], critique_notes: str
) -> list[str]:
    if not source_text or not source_text.strip():
        return []
    source = " ".join(source_text.split())
    claims = " ".join(
        str(value)
        for risk in risks
        for key in ("title", "description")
        if (value := risk.get(key)) is not None
    )
    critic = critique_notes or ""
    combined = f"{claims} {critic}"
    issues: list[str] = []

    # A contract clause says the Contractor must rectify defects within an
    # explicit notice period: the model cannot claim there is no period.
    rectification_deadline = re.search(
        r"\bdefective\s+work\b[^.]{0,260}\bwithin\s+(?:[a-z-]+\s+)?(?:\(\d{1,3}\)|\d{1,3})"
        r"\s+days?\s+of\s+written\s+notice\b",
        source, re.IGNORECASE,
    )
    missing_period = re.search(
        r"\b(?:no|without|lacks?|lacking)\s+"
        r"(?:(?:an?|the|agreed|defined|specified|clear|any)\s+){0,4}"
        r"(?:rectification\s+)?(?:time\s?frame|deadline|period)\b",
        combined, re.IGNORECASE,
    )
    if rectification_deadline and missing_period:
        issues.append(
            "Defect rectification: source specifies a deadline after written notice, "
            "but the analysis claims no deadline. Correct the risk description and severity."
        )
    if rectification_deadline and re.search(
        r"\b(?:clause\s+)?5\.2\b.{0,45}\b(?:truncat\w*|anonymis\w*|anonymiz\w*)\b",
        critic, re.IGNORECASE,
    ):
        issues.append(
            "Clause 5.2: unsupported truncation/anonymisation allegation; "
            "the available source has an explicit rectification deadline."
        )

    # A contractual cure period and the definition of material breach are
    # different issues. Do not present the former as missing when it is stated.
    if re.search(
        r"\bmaterial\s+breach\s+not\s+remedied\s+within\s+"
        r"(?:[a-z-]+\s+)?(?:\(\d{1,3}\)|\d{1,3})\s+days?\s+of\s+written\s+notice",
        source, re.IGNORECASE,
    ) and re.search(
        r"\b(?:no|without|lacks?)\s+(?:(?:an?|the|defined|clear|specified)\s+){0,4}"
        r"cure\s+period\b",
        combined, re.IGNORECASE,
    ):
        issues.append(
            "Termination: source states a cure period for material breach. "
            "Distinguish this from uncertainty about the meaning of material breach."
        )

    # Where the Client owes progress payments, don't reassign the Client's
    # delay to the Contractor as if it were the Contractor's payment default.
    if re.search(r"\bClient\s+shall\s+pay\b", source, re.IGNORECASE) and re.search(
        r"\bpayment\s+delay\b.{0,130}\bmaterial\s+breach\s+by\s+(?:the\s+)?Contractor\b",
        combined, re.IGNORECASE,
    ):
        issues.append(
            "Payment: the Client owes progress payments under the supplied source; "
            "a Client payment delay cannot be attributed to the Contractor as payer."
        )
    return issues


from src.analysis.domain.ai_extraction import (
    AIExtractionPort,
    CritiqueExtractionService,
)
from src.analysis.domain.critique_evaluation import CritiqueEvaluationService


@dataclass(frozen=True)
class CritiqueExtractionCommand:
    extracted_risks: list[dict[str, Any]]
    extracted_wbs: list[dict[str, Any]]
    doc_type: str | None
    retry_count: int
    source_text: str | None = None


@dataclass(frozen=True)
class CritiqueExtractionResult:
    status: str               # "OK" | "RETRY"
    notes_raw: str            # the critique note as returned by the LLM
    confidence: float | None
    retry_count: int
    human_approval_required: bool
    critique_notes: str       # possibly cleared by evaluation (OK → "")


@dataclass(frozen=True)
class CritiqueExtractionUseCase:
    ai: AIExtractionPort
    extraction_service: CritiqueExtractionService = field(
        default_factory=CritiqueExtractionService
    )
    evaluation_service: CritiqueEvaluationService = field(
        default_factory=CritiqueEvaluationService
    )

    async def execute(self, cmd: CritiqueExtractionCommand) -> CritiqueExtractionResult:
        items = cmd.extracted_risks if cmd.extracted_risks else cmd.extracted_wbs
        confidence = self.evaluation_service.calculate_confidence(items)

        critique = await self.extraction_service.extract(
            items=items,
            doc_type=cmd.doc_type or "unknown",
            ai=self.ai,
            source_text=cmd.source_text,
        )

        source_issues = (
            _source_consistency_issues(
                source_text=cmd.source_text,
                risks=cmd.extracted_risks,
                critique_notes=critique.notes,
            )
            if cmd.doc_type == "contract"
            else []
        )
        if source_issues:
            # Independent of the LLM's "OK" verdict: a source-backed
            # contradiction is an explicit human-review stop. Keep the
            # unverified LLM notes intact rather than rewriting audit history.
            notes = "SOURCE CONSISTENCY CHECK — correction required:\n" + "\n".join(
                f"- {issue}" for issue in source_issues
            )
            if critique.notes:
                notes += "\nOriginal AI critique (unverified):\n" + critique.notes
            evaluation = self.evaluation_service.evaluate_critique(
                critique_status="RETRY",
                critique_notes=notes,
                confidence=None,
                retry_count=cmd.retry_count,
            )
            return CritiqueExtractionResult(
                status="RETRY",
                notes_raw=critique.notes,
                confidence=None,
                retry_count=evaluation.retry_count,
                human_approval_required=True,
                critique_notes=notes,
            )

        evaluation = self.evaluation_service.evaluate_critique(
            critique_status=critique.status,
            critique_notes=critique.notes,
            confidence=confidence,
            retry_count=cmd.retry_count,
        )

        return CritiqueExtractionResult(
            status=critique.status,
            notes_raw=critique.notes,
            confidence=confidence,
            retry_count=evaluation.retry_count,
            human_approval_required=evaluation.human_approval_required,
            critique_notes=evaluation.critique_notes,
        )
