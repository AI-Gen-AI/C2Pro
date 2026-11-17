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

from src.analysis.domain.ai_extraction import (
    AIExtractionPort,
    CritiqueExtractionService,
)
from src.analysis.domain.critique_evaluation import CritiqueEvaluationService

# No contractual keyword or clause pattern may decide the meaning of an
# obligation. N12 consults the model and grounded evidence, and abstains when
# interpretation is not independently validated. Business rules belong outside
# this service. See #1049 / owner approval dated 2026-11-17.
# A second N12 pass must not resend the whole N2 projection. Select only
# verbatim N4 quotations with nearby context; never treat this as full coverage.
_N12_FOCAL_CONTEXT_CHARS = 300
_N12_FOCAL_MAX_CHARS = 8_000
_N12_FOCAL_MAX_ITEMS = 12


def _n12_focal_source(
    source_text: str | None, items: list[dict[str, Any]]
) -> str:
    source = source_text or ""
    if not source:
        return ""
    ranges: list[tuple[int, int]] = []
    for item in items[:_N12_FOCAL_MAX_ITEMS]:
        if not isinstance(item, dict):
            continue
        # A rejected quote cannot become a source pointer through N12.
        if item.get("source_quote_status") in (
            "NOT_FOUND_IN_DOCUMENT", "NOT_FOUND", "MISSING_QUOTE",
            "SOURCE_UNAVAILABLE",
        ):
            continue
        quote = item.get("source_quote")
        if not isinstance(quote, str) or not 24 <= len(quote) <= 2_000:
            continue
        offset = source.find(quote)
        if offset == -1:
            continue
        ranges.append((
            max(0, offset - _N12_FOCAL_CONTEXT_CHARS),
            min(len(source), offset + len(quote) + _N12_FOCAL_CONTEXT_CHARS),
        ))
    if not ranges:
        return ""
    merged: list[list[int]] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(end, merged[-1][1])
        else:
            merged.append([start, end])
    chunks: list[str] = []
    remaining = _N12_FOCAL_MAX_CHARS
    for start, end in merged:
        # Do not silently truncate a clause. The omitted span stays unassessed.
        span = source[start:end]
        if len(span) > remaining:
            break
        chunks.append(f"[source offset {start}:{end}]\n{span}")
        remaining -= len(span) + 70
        if remaining <= 0:
            break
    excerpt = "\n\n".join(chunks)
    # A small document has no economical focal review; direct to human instead.
    if not excerpt or len(excerpt) >= len(source) * 0.8:
        return ""
    return excerpt


@dataclass(frozen=True)
class CritiqueExtractionCommand:
    extracted_risks: list[dict[str, Any]]
    extracted_wbs: list[dict[str, Any]]
    doc_type: str | None
    retry_count: int
    source_text: str | None = None
    # Set True only from a trusted upstream coverage record for this revision.
    # Neither presence nor short length of text proves complete parsing.
    source_complete: bool | None = None


@dataclass(frozen=True)
class CritiqueExtractionResult:
    status: str               # "OK" | "RETRY" | "UNASSESSED"
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

        if cmd.retry_count > 0:
            # WBS 1.4: a repeat critique is never another whole-document call.
            # Re-evaluate only source-backed candidate spans. A focal pass
            # cannot certify omitted obligations outside those spans.
            focused = _n12_focal_source(cmd.source_text, items)
            if not focused:
                return CritiqueExtractionResult(
                    status="UNASSESSED", notes_raw="", confidence=None,
                    retry_count=cmd.retry_count, human_approval_required=True,
                    critique_notes=(
                        "N12_FOCAL_NOT_AVAILABLE: no bounded source-backed "
                        "target; repeat whole-source call skipped. "
                        "Human review required."
                    ),
                )
            focal = await self.extraction_service.extract(
                items=items,
                doc_type=cmd.doc_type or "unknown",
                ai=self.ai,
                source_text=focused,
                source_complete=False,
                review_scope="focal",
            )
            return CritiqueExtractionResult(
                status="UNASSESSED",
                notes_raw=focal.notes,
                confidence=None,
                retry_count=cmd.retry_count,
                human_approval_required=True,
                critique_notes=(
                    "N12_FOCAL_ONLY: bounded source-backed recheck, "
                    f"{len(focused)}/{len(cmd.source_text or '')} source chars "
                    "submitted; document-wide recall NOT assessed. "
                    "Human review required. "
                    + focal.notes[:2400]
                ),
            )

        critique = await self.extraction_service.extract(
            items=items,
            doc_type=cmd.doc_type or "unknown",
            ai=self.ai,
            source_text=cmd.source_text,
            source_complete=cmd.source_complete,
        )
        # N4's extraction confidence is not an assessment of N12.  Once the
        # critic cannot substantiate its verdict, keep that uncertainty rather
        # than letting a high N4 score waive the existing HITL gate.
        assessed_confidence = None if critique.status == "UNASSESSED" else confidence

        evaluation = self.evaluation_service.evaluate_critique(
            critique_status=critique.status,
            critique_notes=critique.notes,
            confidence=assessed_confidence,
            retry_count=cmd.retry_count,
        )

        return CritiqueExtractionResult(
            status=critique.status,
            notes_raw=critique.notes,
            confidence=assessed_confidence,
            retry_count=evaluation.retry_count,
            # A model self-report of OK, or high candidate confidence, is
            # never human acceptance. N3 routes both "contract" and "other"
            # into N4, and newly proposed risks from ANY document family
            # must reach HITL. Do not restrict this gate to EPC/contracts.
            human_approval_required=(
                evaluation.human_approval_required
                or bool(cmd.extracted_risks)
            ),
            critique_notes=evaluation.critique_notes,
        )
