"""
C2Pro - Asynchronous Ingestion Tasks

This module defines Celery tasks related to document ingestion and processing.
These tasks are designed to run in the background, decoupled from the main
API request/response cycle.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
import re
from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text

from src.analysis.adapters.graph.review_lineage import (
    claim_review_lineage_for_current_attempt,
)
from src.analysis.adapters.graph.workflow import close_checkpointer_resources
from src.analysis.factories.orchestrator_factory import AnalysisOrchestratorFactory
from src.core import checkpoint_lineage, processing_authority
from src.core.database import close_db, get_raw_session, init_db
from src.core.dlq.dlq_service import DLQService
from src.core.processing_authority import (
    ProcessingAuthority,
    ProcessingAuthorityLost,
    ProcessingPhase,
    ProcessingStage,
)
from src.core.tasks.async_runtime import run_async_db_task
from src.core.tasks.celery_app import celery_app
from src.core.tenants.types import TenantId, require_tenant_id
from src.documents.adapters.extraction.documents_entity_extraction_service import (
    DocumentsEntityExtractionService,
)
from src.documents.adapters.parsers.bc3_file_parser import BC3FileParser
from src.documents.adapters.parsers.composite_file_parser import CompositeFileParser
from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser
from src.documents.adapters.parsers.pdf_file_parser import PDFFileParser
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.adapters.rag.sqlalchemy_rag_ingestion_service import (
    SqlAlchemyRagIngestionService,
)
from src.documents.adapters.storage.factory import build_storage_service
from src.documents.application.document_source import (
    REVISION_HASH_MISMATCH,
    RevisionSourceError,
    fetch_source_file,
    resolve_source_revision,
)
from src.documents.application.revision_clauses import persist_revision_clauses
from src.documents.application.trigger_document_analysis_use_case import (
    TriggerDocumentAnalysisUseCase,
)
from src.documents.domain.models import Clause, ClauseType, DocumentStatus, DocumentType
from src.documents.ports.rag_ingestion_service import RagIngestionOutcome
from src.procurement.adapters.persistence.bom_repository import SQLAlchemyBOMRepository
from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
from src.procurement.application.use_cases.bom_use_cases import CreateBOMItemUseCase
from src.procurement.application.use_cases.wbs_use_cases import CreateWBSItemUseCase
from src.stakeholders.adapters.persistence.sqlalchemy_stakeholder_repository import (
    SqlAlchemyStakeholderRepository,
)
from src.stakeholders.application.create_stakeholder_use_case import CreateStakeholderUseCase
from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.application.change_projection import build_revision_processing_failed_event
from src.temporal.application.revision_change_orchestrator import (
    build_revision_analysis_events,
    snapshot_clauses_for_revision,
)
from src.temporal.domain.document_revision import DocumentRevision

logger = logging.getLogger(__name__)

RAG_READINESS_MAX_RETRIES = 3
PROCESSING_HEARTBEAT_INTERVAL_SECONDS = 60

async def _document_processing_heartbeat_loop(
    *,
    authority: ProcessingAuthority,
    interval_seconds: float = PROCESSING_HEARTBEAT_INTERVAL_SECONDS,
) -> None:
    """Renew this attempt's DB-clock lease while the worker is alive.

    #711: a heartbeat renews only the EXACT attempt (attempt, owner token,
    fence, revision, generation, stage) and only while its lease is still
    valid. Once it is refused, authority is gone: stop renewing. The worker's
    fenced writes fail closed on their own; heartbeat freshness is never
    authority by itself.
    """
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            async with get_raw_session() as heartbeat_session:
                renewed = await processing_authority.heartbeat(heartbeat_session, authority)
                if renewed:
                    await heartbeat_session.commit()
                else:
                    await heartbeat_session.rollback()
        except asyncio.CancelledError:
            raise
        except Exception:
            # Primary processing remains authoritative; a failed heartbeat is
            # observable but must not mask the task's real outcome.
            logger.exception(
                "document_processing_heartbeat_failed",
                extra={
                    "document_id": str(authority.document_id),
                    "fencing_token": authority.fencing_token,
                },
            )
            continue
        if not renewed:
            logger.warning(
                "document_processing_authority_lost",
                extra={
                    "document_id": str(authority.document_id),
                    "stage": authority.stage.value,
                    "fencing_token": authority.fencing_token,
                },
            )
            return


async def _stop_processing_heartbeat(task: asyncio.Task[None] | None) -> None:
    if task is None:
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


def _build_text_block_index(text_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build offset + coordinate-space index for flattened parsed text.

    Offsets correspond to the exact string produced by joining blocks with
    "\n\n". PyMuPDF/OCR bboxes are absolute PDF-page coordinates; a future
    producer may explicitly declare normalized geometry.
    """
    index: list[dict[str, Any]] = []
    pos = 0
    for i, block in enumerate(text_blocks):
        txt = block.get("text", "") if isinstance(block.get("text"), str) else ""
        start = pos
        end = start + len(txt)
        raw_bbox = block.get("bbox")
        has_bbox = isinstance(raw_bbox, (list, tuple)) and len(raw_bbox) == 4
        explicit_normalized = block.get("normalized")
        index.append(
            {
                "start_offset": start,
                "end_offset": end,
                "page": block.get("page"),
                "bbox": raw_bbox,
                "normalized": (
                    explicit_normalized
                    if isinstance(explicit_normalized, bool)
                    else False
                )
                if has_bbox
                else False,
                "text": txt,
            }
        )
        pos = end
        if i < len(text_blocks) - 1:
            pos += 2
    return index


def _temporal_failure_code(error: Exception) -> str:
    """Return a stable safe code; raw errors can contain storage/provider data."""
    if isinstance(error, RevisionSourceError) and str(error) == REVISION_HASH_MISMATCH:
        return "immutable_blob_hash_mismatch"
    return "analysis_processing_failed"


class RagChunksUnavailableError(RuntimeError):
    """TS-UD-OPS-DOCFLOW-B-001: analysis must not run before RAG evidence commits."""

file_parser = CompositeFileParser(
    bc3_parser=BC3FileParser(),
    excel_parser=ExcelFileParser(),
    pdf_parser=PDFFileParser(),
)


@celery_app.task(name="handle_failed_task")
def handle_failed_task(**kwargs: Any) -> dict[str, Any]:
    """Compatibility task for deferred failure handling."""
    return kwargs


def _build_processing_details(extraction_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "processing_stage": "parsed_pending_analysis",
        "analysis_status": "queued",
        "status_detail": (
            "Document parsing and downstream extraction completed. Analysis orchestration queued."
        ),
        "extraction_summary": extraction_summary,
    }


def _infer_contract_clause_type(text: str) -> ClauseType:
    lowered = text.lower()
    if any(term in lowered for term in ["penalt", "liquidated damages", "delay"]):
        return ClauseType.PENALTY
    if any(term in lowered for term in ["payment", "invoice", "certified"]):
        return ClauseType.PAYMENT
    if any(term in lowered for term in ["warranty", "defect", "liability"]):
        return ClauseType.WARRANTY
    if any(term in lowered for term in ["scope", "includes", "works", "deliverable"]):
        return ClauseType.SCOPE
    if any(term in lowered for term in ["milestone", "deadline", "completion", "schedule"]):
        return ClauseType.DELIVERY
    return ClauseType.OTHER


def _parse_money_number(raw: str) -> float | None:
    if not raw:
        return None
    compact = raw.replace(" ", "")
    if "," in compact and "." in compact:
        if compact.rfind(",") > compact.rfind("."):
            normalized = compact.replace(".", "").replace(",", ".")
        else:
            normalized = compact.replace(",", "")
    elif "," in compact:
        left, right = compact.rsplit(",", 1)
        if len(right) in {1, 2}:
            normalized = f"{left.replace(',', '')}.{right}"
        else:
            normalized = compact.replace(",", "")
    else:
        parts = compact.split(".")
        if len(parts) > 2 and all(len(part) == 3 for part in parts[1:]):
            normalized = compact.replace(".", "")
        else:
            normalized = compact
    try:
        return float(normalized)
    except ValueError:
        return None


def _extract_numeric_money(text: str) -> float | None:
    match = re.search(
        r"(?:eur|€)\s*(\d[\d.,]*)|(\d[\d.,]*)\s*(?:eur|€)", text, re.IGNORECASE
    )
    if not match:
        return None
    return _parse_money_number(match.group(1) or match.group(2) or "")


_CONTRACT_LABEL_RE = re.compile(
    r"(?:"
    # Spanish
    r"presupuesto\s+base(?:\s+de\s+licitaci[oó]n)?|"
    r"importe\s+(?:del\s+)?contrato|"
    r"precio\s+(?:del\s+)?contrato|"
    r"valor\s+(?:estimado\s+)?(?:del\s+)?contrato|"
    r"importe\s+de\s+adjudicaci[oó]n|"
    # English
    r"(?:total\s+)?contract\s+(?:price|value|sum|amount)|"
    r"lump\s+sum\s+(?:contract\s+)?(?:price|value|amount)?|"
    r"award(?:ed)?\s+(?:contract\s+)?(?:price|value|sum|amount)"
    r")",
    re.IGNORECASE,
)

_CRORE_LAKH_RE = re.compile(r"\s*(crore|cr\.?|lakhs?|lac)\b", re.IGNORECASE)


def _extract_contract_base_total(text: str) -> float | None:
    """Extract contract base total from clause text.

    Handles Spanish + English labels, EUR/₹/Rs./INR currency markers, and INR
    crore/lakh notation. Returns the largest labeled amount found, or None.
    """
    candidates: list[float] = []
    for label_m in _CONTRACT_LABEL_RE.finditer(text):
        window_start = label_m.start() + len(label_m.group(0))
        window = text[window_start:window_start + 250]

        # Prefer INR-prefixed number (₹, Rs., INR); fall back to bare number.
        raw_num: str | None = None
        num_end = 0
        inr_m = re.search(
            r"(?:₹|Rs\.?\s*|INR\s*)(\d[\d,.]*)", window, re.IGNORECASE
        )
        if inr_m:
            raw_num = inr_m.group(1)
            num_end = inr_m.end()
        else:
            bare_m = re.search(r"[^\d₹](\d[\d,.]*)", window)
            if bare_m:
                raw_num = bare_m.group(1)
                num_end = bare_m.end()

        if raw_num is None:
            continue

        after_num = window[num_end:num_end + 15]
        crore_m = _CRORE_LAKH_RE.match(after_num)
        if crore_m:
            unit = crore_m.group(1).lower().rstrip(".")
            multiplier = 1e7 if unit.startswith("cr") else 1e5
            v = _parse_money_number(raw_num)
            if v is not None:
                candidates.append(v * multiplier)
        else:
            v = _parse_money_number(raw_num)
            # Sanity: genuine contract totals exceed 10,000
            if v is not None and v > 10_000:
                candidates.append(v)

    return max(candidates) if candidates else None


def _detect_contract_currency(text: str) -> str:
    """Return 'INR' if text contains INR markers, else 'EUR'."""
    if re.search(
        r"₹|Rs\.?\s*\d|\bINR\b|\brupee\b|\bcrore\b|\blakh\b", text, re.IGNORECASE
    ):
        return "INR"
    return "EUR"


def _extract_percentage(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if not match:
        return None
    try:
        return float(match.group(1)) / 100.0
    except ValueError:
        return None


def _extract_days(text: str) -> int | None:
    match = re.search(r"(\d+)\s*(?:days?|días)", text, re.IGNORECASE)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _extract_months(text: str) -> int | None:
    match = re.search(r"(\d+)\s*(?:months?|mes(?:es)?)", text, re.IGNORECASE)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


# Terms that mark a coherence category regardless of the inferred clause_type. A
# clause-sized chunk usually spans several topics, so category coverage is derived
# from the text, not only from a single dominant type.
_CLAUSE_KEYWORD_CATEGORIES: dict[str, tuple[str, ...]] = {
    "SCOPE": ("objeto", "obras", "alcance", "prestaci", "scope", "deliverable", "work"),
    "TIME": ("plazo", "deadline", "schedule", "milestone", "completion", "duraci", "entrega", "cronograma"),
    "BUDGET": ("precio", "importe", "presupuesto", "coste", "pago", "payment", "budget", "euros", "€"),
    "LEGAL": ("penal", "clausula", "cláusula", "ley", "law", "responsab", "garant", "warranty", "obligaci"),
    "QUALITY": ("calidad", "quality", "inspecci", "inspection", "testing", "ensayo", "norma"),
    "TECHNICAL": ("tecnic", "técnic", "technical", "especificac", "specification", "material"),
}


def _contract_affected_categories(clause_type: ClauseType, text: str) -> list[str]:
    lowered = text.lower()
    categories: list[str] = []

    if clause_type == ClauseType.PENALTY:
        categories.extend(["LEGAL", "TIME"])
        if "%" in text or "penalt" in lowered:
            categories.append("BUDGET")
    elif clause_type == ClauseType.PAYMENT:
        categories.extend(["BUDGET", "LEGAL"])
        if any(term in lowered for term in ["milestone", "certified", "acceptance"]):
            categories.append("TIME")
    elif clause_type == ClauseType.WARRANTY:
        categories.extend(["LEGAL", "QUALITY"])
        if any(term in lowered for term in ["technical", "specification", "performance"]):
            categories.append("TECHNICAL")
    elif clause_type == ClauseType.SCOPE:
        categories.extend(["SCOPE"])
        if any(term in lowered for term in ["material", "specification", "technical"]):
            categories.append("TECHNICAL")
        if any(term in lowered for term in ["inspection", "testing", "acceptance"]):
            categories.append("QUALITY")
    elif clause_type == ClauseType.DELIVERY:
        categories.extend(["TIME", "SCOPE"])
    else:
        categories.append("LEGAL")

    for category, terms in _CLAUSE_KEYWORD_CATEGORIES.items():
        if any(term in lowered for term in terms):
            categories.append(category)

    deduped: list[str] = []
    for category in categories:
        if category not in deduped:
            deduped.append(category)
    return deduped


def _build_contract_clause_data(text: str, parsed_text: str) -> dict[str, Any]:
    clause_type = _infer_contract_clause_type(text)
    affected_categories = _contract_affected_categories(clause_type, text)
    data: dict[str, Any] = {
        "category": affected_categories[0] if affected_categories else "LEGAL",
        "affected_categories": affected_categories,
        "source_document_type": "contract",
        "source": "contract_ingestion_deterministic",
    }

    amount = (
        _extract_contract_base_total(text)
        or _extract_contract_base_total(parsed_text)
        or _extract_numeric_money(text)
        or _extract_numeric_money(parsed_text)
    )
    if amount is not None:
        data["currency"] = _detect_contract_currency(f"{text} {parsed_text}")
        data["planned"] = amount
        data["total_amount"] = amount

    if clause_type == ClauseType.PENALTY:
        pct = _extract_percentage(text)
        if pct is not None:
            data["daily_penalty_pct"] = pct
            data["penalty_cap_pct"] = pct
    if clause_type == ClauseType.PAYMENT:
        days = _extract_days(text)
        if days is not None:
            data["payment_term_days"] = days
    lowered = text.lower()
    if clause_type == ClauseType.DELIVERY or any(
        term in lowered for term in ["schedule", "deadline", "milestone", "completion"]
    ):
        data["status"] = "at_risk"
    if clause_type == ClauseType.WARRANTY:
        months = _extract_months(text)
        if months is not None:
            data["warranty_months"] = months
    if clause_type == ClauseType.MILESTONE:
        deadline = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
        if deadline:
            data["deadline"] = deadline.group(1)
    if clause_type == ClauseType.QUALITY:  # noqa: SIM102
        if any(term in text.lower() for term in ["inspection", "testing", "acceptance"]):
            data["quality_standards"] = ["inspection-testing-acceptance"]
    if clause_type == ClauseType.SCOPE:
        data["deliverables"] = [{"name": text[:120]}]

    return data


# A new clause starts at a numbered header ("28.-", "28.1.-", "1.-"), a section
# keyword (CLÁUSULA / ESTIPULACIÓN / ARTÍCULO / CLAUSE / ARTICLE / SECTION), or an
# ordinal word (PRIMERA … DÉCIMA). Anchored at line start to avoid mid-sentence
# matches. Used to split a contract into clause-sized chunks instead of sentences.
_CLAUSE_BOUNDARY = re.compile(
    r"(?m)^\s*(?:"
    r"\d{1,3}(?:\.\d{1,3}){0,6}\s*\.\s*[-–]"
    r"|(?:CL[ÁA]USULA|ESTIPULACI[ÓO]N|ART[ÍI]CULO|CLAUSE|ARTICLE|SECTION)\w*"
    r"|(?:PRIMERA|SEGUNDA|TERCERA|CUARTA|QUINTA|SEXTA|S[ÉE]PTIMA|OCTAVA|NOVENA|D[ÉE]CIMA)\b"
    r")",
    re.IGNORECASE,
)


def _trimmed_clause_span(
    parsed_text: str,
    start_offset: int,
    end_offset: int,
) -> tuple[str, int, int] | None:
    raw = parsed_text[start_offset:end_offset]
    if not raw.strip():
        return None
    left_trim = len(raw) - len(raw.lstrip())
    right_trim = len(raw) - len(raw.rstrip())
    start = start_offset + left_trim
    end = end_offset - right_trim
    return parsed_text[start:end], start, end


def _split_contract_clause_spans(
    parsed_text: str,
) -> list[tuple[str, int, int]]:
    """Split contract text while preserving exact source offsets."""
    boundaries = [match.start() for match in _CLAUSE_BOUNDARY.finditer(parsed_text)]
    spans: list[tuple[int, int]] = []

    if boundaries:
        cut_points = ([0] if boundaries[0] > 0 else []) + boundaries + [len(parsed_text)]
        spans = [
            (cut_points[index], cut_points[index + 1])
            for index in range(len(cut_points) - 1)
        ]
    else:
        cursor = 0
        for separator in re.finditer(r"\n\s*\n+", parsed_text):
            spans.append((cursor, separator.start()))
            cursor = separator.end()
        spans.append((cursor, len(parsed_text)))

    result: list[tuple[str, int, int]] = []
    for start, end in spans:
        trimmed = _trimmed_clause_span(parsed_text, start, end)
        if trimmed is not None:
            result.append(trimmed)
    return result


def _split_contract_into_clauses(parsed_text: str) -> list[str]:
    """Compatibility text-only view over the exact clause-span splitter."""
    return [segment for segment, _, _ in _split_contract_clause_spans(parsed_text)]


def _extract_contract_clauses(
    *,
    document_id: UUID,
    project_id: UUID,
    tenant_id: TenantId,
    parsed_text: str,
    parsed_payload: dict[str, Any] | None = None,
    revision_id: UUID | None = None,
) -> list[Clause]:
    clauses: list[Clause] = []
    # Build offset index from text blocks if available
    text_blocks = parsed_payload.get("text_blocks", []) if isinstance(parsed_payload, dict) else []
    block_index = _build_text_block_index(text_blocks) if text_blocks else []
    for index, (segment, start_offset, source_end_offset) in enumerate(
        _split_contract_clause_spans(parsed_text),
        start=1,
    ):
        if len(segment) < 40:
            continue
        segment = segment[:4000]  # keep a clause clause-sized; guard OCR blobs
        end_offset = min(source_end_offset, start_offset + len(segment))
        clause_type = _infer_contract_clause_type(segment)
        # Resolve overlapping blocks
        pages: list[int] = []
        bboxes: list[tuple[tuple[float, float, float, float], bool]] = []
        if block_index:
            for entry in block_index:
                # Overlap check
                if entry["end_offset"] <= start_offset or entry["start_offset"] >= end_offset:
                    continue
                page = entry.get("page")
                if isinstance(page, int):
                    pages.append(page)
                raw_bbox = entry.get("bbox")
                block_text = entry.get("text")
                block_start = entry.get("start_offset")
                block_end = entry.get("end_offset")
                exact_block_span = False
                if (
                    isinstance(block_text, str)
                    and isinstance(block_start, int)
                    and isinstance(block_end, int)
                ):
                    left_trim = len(block_text) - len(block_text.lstrip())
                    right_trim = len(block_text) - len(block_text.rstrip())
                    exact_block_span = (
                        start_offset == block_start + left_trim
                        and end_offset == block_end - right_trim
                    )

                if (
                    exact_block_span
                    and isinstance(raw_bbox, (list, tuple))
                    and len(raw_bbox) == 4
                    and all(isinstance(value, (int, float)) for value in raw_bbox)
                ):
                    x0, y0, x1, y1 = (float(value) for value in raw_bbox)
                    if x1 >= x0 and y1 >= y0:
                        # Parser-native PDF geometry describes the WHOLE text
                        # block. It is exact evidence geometry only when the
                        # clause span covers that complete source block. A
                        # partial overlap keeps its truthful page + offsets
                        # but MUST NOT inherit the block's full rectangle.
                        bboxes.append(
                            (
                                (x0, y0, x1 - x0, y1 - y0),
                                bool(entry.get("normalized", False)),
                            )
                        )
        # Determine truthful location semantics
        unique_pages = sorted(set(pages))
        page_number: int | None = None
        bbox: list[float] | None = None
        bbox_normalized = False
        if len(unique_pages) == 1:
            page_number = unique_pages[0]
            # A single source block has exact geometry. Multiple blocks keep
            # the real page but do not invent a merged rectangle.
            if len(bboxes) == 1:
                bbox = list(bboxes[0][0])
                bbox_normalized = bboxes[0][1]
            else:
                bbox = None
        # Build evidence_location
        evidence_location = {
            "revision_id": str(revision_id) if revision_id else None,
            "page_number": page_number,
            "page_numbers": unique_pages if unique_pages else [],
            "bbox": bbox,
            "normalized": bbox_normalized if bbox is not None else False,
        }
        extracted = _build_contract_clause_data(segment, parsed_text)
        extracted["evidence_location"] = evidence_location
        clauses.append(
            Clause(
                id=uuid4(),
                project_id=project_id,
                tenant_id=tenant_id,
                document_id=document_id,
                clause_code=f"AUTO-{index:03d}",
                clause_type=clause_type,
                title=segment[:80],
                full_text=segment,
                text_start_offset=start_offset,
                text_end_offset=end_offset,
                extracted_entities=extracted,
                extraction_confidence=0.65,
                extraction_model="deterministic-contract-ingestion",
            )
        )
    return clauses


def _dispatch_failed_task(**kwargs: Any) -> None:
    """Schedule deferred failure handling in Celery when available."""
    apply_async = getattr(handle_failed_task, "apply_async", None)
    if callable(apply_async):
        apply_async(kwargs=kwargs)
        return

    logger.warning(
        "handle_failed_task_apply_async_unavailable",
        extra={"task_type": kwargs.get("task_type")},
    )
    handle_failed_task(**kwargs)


async def _push_trigger_failure_to_dlq(
    *,
    tenant_id: TenantId,
    document_id: UUID,
    error: Exception,
) -> None:
    await DLQService().push(
        tenant_id=tenant_id,
        task_type="document_analysis",
        document_id=document_id,
        payload={"document_id": str(document_id)},
        error_message=str(error),
    )


async def get_document_rag_chunk_count(
    *,
    session: Any,
    tenant_id: TenantId,
    document_id: UUID,
) -> int:
    """TS-UD-OPS-DOCFLOW-B-001: count committed tenant-scoped RAG chunks."""
    statement = text(
        """
        SELECT COUNT(*)
        FROM document_chunks
        WHERE tenant_id = CAST(:tenant_id AS uuid)
          AND document_id = CAST(:document_id AS uuid)
        """
    )
    params = {"tenant_id": str(tenant_id), "document_id": str(document_id)}

    result = await session.execute(statement, params)
    return int(result.scalar_one())


async def _run_analysis_graph_best_effort(
    *,
    orchestrator: Any,
    document: Any,
    parsed_text: str,
    tenant_id: TenantId,
    document_id: UUID,
) -> dict[str, Any]:
    """Run the N1-N17 enrichment graph and report its outcome.

    Best-effort by design: a graph failure must not block the document from being
    marked ANALYZED, since its structured extraction already succeeded during
    parsing. The broad catch is intentional — any orchestrator error degrades to
    "no enrichment", never a stuck document.

    Returns a dict with ``analysis_id`` (str | None) and
    ``human_approval_required`` (bool). A LangGraph HITL interrupt is NOT a
    failure: it must be reported distinctly from "graph raised" or "graph ran
    but produced nothing" so the caller never auto-retries a legitimate,
    durably-checkpointed pause (see ``_run_document_analysis``).
    """
    graph_orchestrator = orchestrator or AnalysisOrchestratorFactory.create()
    # #758: the checkpoint thread is scoped to the processing ATTEMPT that
    # owns this run, not shared across every attempt on the document.
    #
    # It remains deterministic -- derived from the authority, never
    # randomized -- so a redelivery that re-adopts the SAME grant recomputes
    # the same thread and resumes its own checkpoint, which is what keeps a
    # retry from re-triggering a fresh HITL interrupt. What changes is that a
    # DIFFERENT attempt (a takeover after a lease expiry, a recovery
    # hand-off, a reprocess) gets a different thread, so a stale worker's
    # LangGraph appends -- which no database fence can prevent, since the
    # saver writes outside our transactions -- land on a lineage nothing
    # current names. Duplicate reviews are prevented by route_for_review's
    # find_active_review guard, which is keyed on the document, not the
    # thread.
    #
    # Injected into initial_state too, since human_interrupt_node reads
    # thread_id from state, not from the run() kwarg alone.
    authority = processing_authority.current_authority()
    thread_id = checkpoint_lineage.analysis_thread_id(
        document_id=document_id,
        authority=authority,
    )
    # Lane C PR-C2: the revision this run analyses is the one the #711
    # authority pinned -- never "the latest upload". It binds the #714 artifact
    # to its revision and lets N12 consult the temporal-review seam.
    pinned_revision = getattr(authority, "revision_id", None) if authority is not None else None
    initial_state: dict[str, Any] = {
        "document_text": parsed_text,
        "project_id": str(document.project_id),
        "document_id": str(document.id),
        "doc_type": getattr(document.document_type, "value", "") if document.document_type else "",
        "tenant_id": str(tenant_id),
        "thread_id": thread_id,
        "document_filename": getattr(document, "filename", None),
        "messages": [],
        "extracted_risks": [],
        "extracted_wbs": [],
        "confidence_score": 0.0,
        "critique_notes": "",
        "human_feedback": "",
        "retry_count": 0,
        "human_approval_required": False,
        "analysis_id": None,
        "document_revision_id": str(pinned_revision) if pinned_revision else None,
        "force_full_pipeline": True,
    }
    # #758: take the existing review's lineage over the moment this attempt
    # becomes authoritative -- BEFORE the graph starts.
    #
    # Claiming it at the HITL gate is too late: from the instant this worker
    # holds the new fence until the graph reaches N13, the active ReviewItem
    # still names the superseded attempt. A human approving in that window
    # resumes the dead lineage, and a direct HITL resume runs outside the
    # processing authority, so the #711 fence cannot stop it -- for a
    # reprocess it would resume an already superseded revision.
    #
    # Deliberately OUTSIDE the try below, which degrades a graph failure to
    # "no enrichment": an unclaimable lineage must fail closed and stay
    # retryable, never proceed to present a review that resumes someone
    # else's checkpoint. The review is briefly unresumable until this
    # attempt's interrupt checkpoint exists, which is the intended state.
    await claim_review_lineage_for_current_attempt(
        thread_id=thread_id,
        tenant_id=str(tenant_id),
        document_id=str(document_id),
    )

    logger.info(
        "document_analysis_task_started",
        extra={"document_id": str(document_id), "tenant_id": str(tenant_id)},
    )
    try:
        result = await graph_orchestrator.run(initial_state, thread_id=thread_id)
    except Exception:
        logger.exception(
            "document_analysis_graph_failed_nonfatal",
            extra={"document_id": str(document_id), "tenant_id": str(tenant_id)},
        )
        return {"analysis_id": None, "human_approval_required": False}
    analysis_id = result.get("analysis_id")
    human_approval_required = bool(result.get("human_approval_required", False))
    return {
        "analysis_id": analysis_id if isinstance(analysis_id, str) else None,
        "human_approval_required": human_approval_required,
    }


# Retry policy for ``documents.analyze_document``, declared once so the task and
# the test that guards it cannot drift apart. ``AnalysisIncompleteRetryableError``
# is only useful because ``autoretry_for`` catches it; if that were ever removed,
# every transient failure would silently become a one-shot give-up.
ANALYSIS_MAX_RETRIES = 3

ANALYSIS_TASK_RETRY_OPTIONS: dict[str, Any] = {
    "autoretry_for": (Exception,),
    "retry_kwargs": {"max_retries": ANALYSIS_MAX_RETRIES},
    "retry_backoff": True,
    "retry_backoff_max": 60,
}


class AnalysisIncompleteRetryableError(RuntimeError):
    """Analysis did not complete, and retrying it is worthwhile.

    ``process_document_analysis_async`` declares ``autoretry_for=(Exception,)``
    with ``max_retries=3``, so raising is the ONLY way to obtain an automatic
    retry: a normal return -- however honest its payload -- is a completed task
    to Celery. Leaving a document in a re-enterable state is not a retry; this
    exception is what actually re-enqueues one.

    Raised only AFTER the degraded status has been committed, so the document is
    already durably honest even if every retry is exhausted.
    """


# Document types whose product value depends on the N1-N17 free-text graph.
# Grounded in DOC_TYPES ("contract", "technical_spec", "budget", "schedule") and
# in how parsing treats them: schedule/budget are completed by structured WBS/BOM
# extraction and legitimately never need the text graph.
TEXT_ANALYSIS_DOCUMENT_TYPES: frozenset[DocumentType] = frozenset(
    {
        DocumentType.CONTRACT,
        DocumentType.TECHNICAL_SPEC,
        DocumentType.SPECIFICATION,
    }
)


def requires_text_analysis(
    document_type: DocumentType | None, parsed_text: str | None
) -> bool:
    """Whether this document's analysis is incomplete without the N1-N17 graph.

    Deliberately NOT ``bool(parsed_text)`` alone. ``composite_file_parser``
    emits ``text_blocks`` for ANY PDF or DOCX, so a schedule or budget uploaded
    as a PDF carries incidental parsed text. Keying on text alone would hold
    those documents pending forever for a graph they never needed -- trading the
    old false-success bug for a false-incomplete one.

    A structured document is complete via WBS/BOM extraction; only a free-text
    document that actually has text can be owed a graph run.
    """
    if document_type not in TEXT_ANALYSIS_DOCUMENT_TYPES:
        return False
    return bool(parsed_text)


def decide_document_status(
    *,
    requires_text_analysis: bool,
    rag_chunk_count: int,
    graph_analysis_id: str | None,
) -> DocumentStatus:
    """Decide whether a document may be called ANALYZED.

    ANALYZED has to mean the analysis this document actually needed completed.
    Previously it was set unconditionally, so a contract whose N1-N17 graph never
    ran was indistinguishable from one fully analysed -- the shape observed in
    production, where a contract reached ANALYZED with zero RAG chunks, zero
    analyses and zero snapshots.

    Structured documents (schedule/budget) carry no free text, so no graph is
    required and zero chunks is their correct terminal outcome. Only free-text
    documents that genuinely needed the graph can be held back.

    PARSED_PENDING_ANALYSIS is reused rather than adding a new enum value: it
    already means "ingestion complete, analysis not yet started", it already
    satisfies ``Document.is_parsed()``, and ``_run_document_analysis`` accepts
    parsed documents -- so the degraded state is retryable by construction
    instead of being a dead end.
    """
    if not requires_text_analysis:
        return DocumentStatus.ANALYZED
    if rag_chunk_count > 0 and graph_analysis_id:
        return DocumentStatus.ANALYZED
    return DocumentStatus.PARSED_PENDING_ANALYSIS


def should_retry_analysis(
    *,
    status: DocumentStatus,
    rag_outcome: str | None,
) -> bool:
    """Whether an incomplete analysis is worth re-enqueueing automatically.

    A completed document never retries. Beyond that the distinction is whether
    anything could plausibly change on its own:

    - MISCONFIGURED: an operator must set configuration. Three backoff retries
      would burn a worker and change nothing, and the resulting task failure
      would misreport a config problem as a transient one. Return normally
      instead, leaving the document pending for an operator.
    - PROVIDER_UNAVAILABLE / unknown / graph failure: plausibly transient, so
      take the bounded automatic retry the task already declares.

    Either way the document has already been persisted as incomplete, so
    exhausting the retries never yields ANALYZED.
    """
    if status is DocumentStatus.ANALYZED:
        return False
    return rag_outcome != RagIngestionOutcome.MISCONFIGURED.value


async def _run_document_analysis(
    *,
    tenant_id: TenantId,
    document_id: UUID,
    orchestrator: Any = None,
    automatic_retry_available: bool = False,
    generation: int | None = None,
    authority: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Analyze a parsed document; the N1-N17 graph is a best-effort enrichment.

    #711: runs only under the document's ANALYSIS authority. The authority is
    bound for the graph run, so every durable seam the graph reaches (HITL
    review routing, checkpoint attach, N17 persistence, graph events, node
    error evidence, the artifact completion hook) re-verifies it in its own
    transaction; the terminal status/metadata write is fenced the same way.
    A worker that lost authority returns ``authority_lost`` and writes
    nothing -- no status, no retry, no DLQ entry.
    """
    await init_db()

    async with get_raw_session() as session:
        repo = SqlAlchemyDocumentRepository(session=session)
        document = await repo.get_by_id(tenant_id, document_id)
        if not document:
            raise ValueError("document not found or access denied")
        # Redelivery after the durable terminal seam must not replay graph
        # side effects.
        if document.upload_status is DocumentStatus.ANALYZED:
            return {
                "status": "already_complete",
                "document_id": str(document_id),
                "document_status": DocumentStatus.ANALYZED.value,
            }
        if not document.is_parsed():
            raise ValueError("document must be parsed before analysis")

        grant, claim_outcome = await _claim_processing(
            session,
            tenant_id=tenant_id,
            document_id=document_id,
            stage=ProcessingStage.ANALYSIS,
            revision_id=None,
            generation=generation,
            authority=authority,
        )
        if grant is None:
            await session.rollback()
            logger.info(
                "document_analysis_not_owned",
                extra={"document_id": str(document_id), "outcome": claim_outcome},
            )
            return {"status": claim_outcome, "document_id": str(document_id)}
        await session.commit()

        heartbeat = asyncio.create_task(_document_processing_heartbeat_loop(authority=grant))
        try:
            with processing_authority.bound_authority(grant):
                outcome = await _analyze_owned(
                    session=session,
                    repo=repo,
                    document=document,
                    tenant_id=tenant_id,
                    document_id=document_id,
                    orchestrator=orchestrator,
                    automatic_retry_available=automatic_retry_available,
                    grant=grant,
                )
        except ProcessingAuthorityLost as lost:
            await session.rollback()
            return _authority_lost_result(document_id=document_id, grant=grant, error=lost)
        except Exception as error:
            await session.rollback()
            await _release_analysis_after_failure(session, grant, error)
            raise
        finally:
            await _stop_processing_heartbeat(heartbeat)

    result, retry, retry_error = outcome
    # Raised outside the session block: the degraded status is already committed,
    # so the document stays honestly incomplete even when every retry is spent.
    if retry:
        raise AnalysisIncompleteRetryableError(retry_error)
    return result


async def _release_analysis_after_failure(
    session: Any, grant: ProcessingAuthority, error: Exception
) -> None:
    """Give the lease back (still owned) so Celery's retry can take a new fence."""
    try:
        await processing_authority.settle(
            session,
            grant,
            phase=ProcessingPhase.PENDING,
            outcome="analysis_failed",
            error=str(error),
        )
        await session.commit()
    except ProcessingAuthorityLost:
        await session.rollback()
    except Exception:  # noqa: BLE001 - the primary analysis error must surface.
        await session.rollback()
        logger.exception(
            "document_analysis_lease_release_failed",
            extra={"document_id": str(grant.document_id)},
        )


async def _analyze_owned(
    *,
    session: Any,
    repo: SqlAlchemyDocumentRepository,
    document: Any,
    tenant_id: TenantId,
    document_id: UUID,
    orchestrator: Any,
    automatic_retry_available: bool,
    grant: ProcessingAuthority,
) -> tuple[dict[str, Any], bool, str]:
    parsed_text = (
        document.document_metadata.get("parsed_text") if document.document_metadata else None
    )
    chunk_count = await get_document_rag_chunk_count(
        session=session,
        tenant_id=tenant_id,
        document_id=document_id,
    )

    # The N1-N17 text-analysis graph only applies to free-text documents that
    # have RAG chunks. Structured documents (schedule/budget) carry no free
    # text, and text documents whose embeddings are unavailable (e.g. no
    # OPENAI_API_KEY -> zero chunks) cannot run it either. In both cases the
    # document is still ANALYZED via the structured extraction (clauses / WBS
    # / BOM) done during parsing — the graph is a best-effort enrichment, never
    # a hard gate. This is what previously stranded documents in
    # parsed_pending_analysis and the DLQ ("parsed_text not available" /
    # "RAG chunks were not committed").
    human_approval_required = False
    if parsed_text and chunk_count > 0:
        graph_result = await _run_analysis_graph_best_effort(
            orchestrator=orchestrator,
            document=document,
            parsed_text=parsed_text,
            tenant_id=tenant_id,
            document_id=document_id,
        )
        analysis_id = graph_result["analysis_id"]
        human_approval_required = graph_result["human_approval_required"]
    else:
        analysis_id = None
        logger.info(
            "document_analysis_graph_skipped",
            extra={
                "document_id": str(document_id),
                "tenant_id": str(tenant_id),
                "reason": "no_parsed_text" if not parsed_text else "no_rag_chunks",
            },
        )

    # Structured extraction completing is not the same claim as the analysis
    # completing. A free-text contract whose graph never ran stays in a
    # retryable state instead of advertising success it does not have.
    status = decide_document_status(
        requires_text_analysis=requires_text_analysis(
            document.document_type, parsed_text
        ),
        rag_chunk_count=chunk_count,
        graph_analysis_id=analysis_id,
    )
    await repo.update_status(tenant_id, document_id, status)
    completed = status is DocumentStatus.ANALYZED
    rag_outcome = (
        document.document_metadata.get("rag_ingestion_outcome")
        if document.document_metadata
        else None
    )
    # A LangGraph HITL interrupt is a legitimate, durably-checkpointed
    # pause -- not a failure, and not "incomplete" in the retryable
    # sense. Auto-retrying it would re-run the whole graph, orphan the
    # pending review, and (pre-fix) mint a duplicate one.
    retry = (
        should_retry_analysis(status=status, rag_outcome=rag_outcome)
        and not human_approval_required
    )

    # #712 truthfulness contract:
    # - while Celery still has an automatic retry available, the durable
    #   user-facing state remains ANALYSIS_PENDING;
    # - FAILED_RETRYABLE is persisted only after the automatic budget is
    #   exhausted, or immediately for a non-retryable incomplete outcome
    #   such as MISCONFIGURED;
    # - HITL pauses are represented by durable review_items instead.
    terminal_incomplete = (
        not completed
        and not human_approval_required
        and (not retry or not automatic_retry_available)
    )
    current_metadata = dict(document.document_metadata or {})
    if current_metadata.get("analysis_last_attempt_incomplete") != terminal_incomplete:
        if terminal_incomplete:
            current_metadata["analysis_last_attempt_incomplete"] = True
        else:
            current_metadata.pop("analysis_last_attempt_incomplete", None)
        await repo.update_metadata(tenant_id, document_id, current_metadata)
    result_status = (
        "waiting_for_review"
        if human_approval_required
        else ("completed" if completed else "incomplete")
    )
    # #711: the terminal write commits only for the exact current owner. Only
    # a completed analysis closes the stage; an incomplete / paused one stays
    # unowned-PENDING so a retry, the recovery sweep or a HITL resume can act.
    await processing_authority.settle(
        session,
        grant,
        phase=ProcessingPhase.COMPLETED if completed else ProcessingPhase.PENDING,
        outcome=result_status,
    )
    await session.commit()
    logger.info(
        "document_analysis_task_finished",
        extra={
            "document_id": str(document_id),
            "tenant_id": str(tenant_id),
            "analysis_id": analysis_id,
            "persisted": bool(analysis_id),
            "document_status": status.value,
            "rag_chunk_count": chunk_count,
            "automatic_retry_available": automatic_retry_available,
            "terminal_incomplete": terminal_incomplete,
        },
    )
    if human_approval_required:
        logger.info(
            "document_analysis_waiting_for_review",
            extra={
                "document_id": str(document_id),
                "tenant_id": str(tenant_id),
                "will_retry": False,
            },
        )
    elif not completed:
        logger.warning(
            "document_analysis_incomplete",
            extra={
                "document_id": str(document_id),
                "tenant_id": str(tenant_id),
                "reason": "no_rag_chunks" if chunk_count == 0 else "graph_did_not_persist",
                "rag_outcome": rag_outcome,
                "will_retry": retry,
            },
        )

    result = {
        "status": result_status,
        "document_id": str(document_id),
        "analysis_id": analysis_id,
        "persisted": bool(analysis_id),
        "document_status": status.value,
        "human_approval_required": human_approval_required,
        "will_retry": retry,
    }
    retry_error = (
        f"document {document_id} analysis incomplete "
        f"(rag_outcome={rag_outcome or 'unknown'}, chunks={chunk_count})"
    )
    return result, retry, retry_error


class _SavepointedUseCase:
    """Run every async call of a use case inside its own SAVEPOINT.

    #711: ingestion stages all of its outputs in ONE transaction that commits
    only after the processing authority is re-verified. A single failing
    extraction row (e.g. a duplicate stakeholder email) must roll back only
    itself, never poison that transaction.
    """

    def __init__(self, session: Any, use_case: Any) -> None:
        self._session = session
        self._use_case = use_case

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._use_case, name)
        if not inspect.iscoroutinefunction(attribute):
            return attribute

        async def _in_savepoint(*args: Any, **kwargs: Any) -> Any:
            async with self._session.begin_nested():
                return await attribute(*args, **kwargs)

        return _in_savepoint


class _StagedStakeholderRepository(SqlAlchemyStakeholderRepository):
    """#711: stakeholders join the fenced ingestion transaction.

    The public use case commits after every insert; inside ingestion that
    commit would publish a stakeholder before the worker's authority is
    verified. Staging (flush) keeps it in the fenced transaction.
    """

    async def commit(self) -> None:
        await self.session.flush()


async def _claim_processing(
    session: Any,
    *,
    tenant_id: UUID,
    document_id: UUID,
    stage: ProcessingStage,
    revision_id: UUID | None,
    generation: int | None,
    authority: Mapping[str, Any] | None,
) -> tuple[ProcessingAuthority | None, str]:
    """Obtain this invocation's processing authority, or say why not.

    A recovery message carries the exact authority the sweep claimed; it is
    adopted once (CLAIMED -> RUNNING) and never replaced by a fresh fence just
    because the message was (re)delivered. Any other invocation acquires, and
    acquire never steals from a valid owner.
    """
    if authority is not None:
        passed = ProcessingAuthority.from_message(authority)
        if (
            passed is None
            or passed.document_id != document_id
            or passed.tenant_id != tenant_id
            or passed.stage is not stage
        ):
            return None, "authority_invalid"
        if await processing_authority.adopt(session, passed):
            return passed, "adopted"
        return None, "authority_lost"
    acquired = await processing_authority.acquire(
        session,
        tenant_id=tenant_id,
        document_id=document_id,
        stage=stage,
        revision_id=revision_id,
        generation=generation,
    )
    return acquired.authority, acquired.outcome.value


def _authority_lost_result(
    *, document_id: UUID, grant: ProcessingAuthority, error: ProcessingAuthorityLost
) -> dict[str, Any]:
    logger.warning(
        "document_processing_authority_lost_before_write",
        extra={
            "document_id": str(document_id),
            "stage": grant.stage.value,
            "fencing_token": grant.fencing_token,
            "reason": str(error),
        },
    )
    return {
        "status": "authority_lost",
        "document_id": str(document_id),
        "stage": grant.stage.value,
        "fencing_token": grant.fencing_token,
    }


async def _process(
    document_id: UUID,
    revision_id: UUID | None = None,
    *,
    generation: int | None = None,
    authority: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Fetch, parse, update, and trigger analysis for a document.

    P0b: the bytes come from the pinned revision's immutable object (or the current
    revision for messages without ``revision_id``), never from a mutable document path.

    #711: the worker first obtains the document's processing authority
    (attempt + owner token + fencing token under a DB-clock lease). Every
    ingestion output -- stakeholders, WBS/BOM, RAG chunks, clauses, revision
    events, metadata and the status hand-over -- is staged in ONE transaction
    that commits only after the authority is re-verified in that same
    transaction. A worker that lost authority (lease expired and taken over,
    or superseded by a new revision / reprocess) commits nothing, and never
    marks the document ERROR on the new owner's behalf.
    """
    await init_db()

    async with get_raw_session() as session:
        repo = SqlAlchemyDocumentRepository(session=session)

        document = await repo.get_by_id_internal(document_id)
        if not document:
            logger.error("Document with ID '%s' not found. Cannot process.", document_id)
            return {"status": "error", "message": "Document not found"}

        def stakeholder_factory() -> Any:
            stk_repo = _StagedStakeholderRepository(session=session)
            return _SavepointedUseCase(
                session,
                CreateStakeholderUseCase(repository=stk_repo, document_repository=repo),
            )

        def wbs_factory() -> Any:
            wbs_repo = SQLAlchemyWBSRepository(session=session)
            return _SavepointedUseCase(session, CreateWBSItemUseCase(wbs_repository=wbs_repo))

        def bom_factory() -> Any:
            bom_repo = SQLAlchemyBOMRepository(session=session)
            return _SavepointedUseCase(session, CreateBOMItemUseCase(bom_repository=bom_repo))

        if document.created_by is None:
            raise ValueError("document has no created_by user_id")
        entity_extraction = DocumentsEntityExtractionService(
            stakeholder_use_case_factory=stakeholder_factory,
            wbs_use_case_factory=wbs_factory,
            bom_use_case_factory=bom_factory,
            user_id=document.created_by,
        )
        rag_ingestion = SqlAlchemyRagIngestionService(db_session=session, commit=False)

        raw_tenant_id = await repo.get_project_tenant_id(document.project_id)
        if not raw_tenant_id:
            logger.error("tenant_id_not_found_for_project: project_id=%s", document.project_id)
            return {"status": "error", "message": "Project not found"}
        tenant_id = require_tenant_id(raw_tenant_id)

        # ACK-loss redelivery after either durable seam is a no-op.
        if document.upload_status is DocumentStatus.ANALYZED:
            return {
                "status": "already_complete",
                "document_id": str(document_id),
                "document_status": DocumentStatus.ANALYZED.value,
            }
        if document.upload_status is DocumentStatus.PARSED_PENDING_ANALYSIS:
            return {
                "status": "already_ingested",
                "document_id": str(document_id),
                "document_status": DocumentStatus.PARSED_PENDING_ANALYSIS.value,
            }

        # Resolve the pinned revision read-only BEFORE any write: a task pinned
        # to an older revision that arrives after a newer one became current
        # may remain historical evidence but must never move the mutable
        # document state backwards (not even to PARSING).
        revision_repository = SqlAlchemyDocumentRevisionRepository(session)
        source_revision: DocumentRevision | None = None
        resolution_error: Exception | None = None
        try:
            source_revision = await resolve_source_revision(
                revision_repository=revision_repository,
                document_id=document_id,
                tenant_id=tenant_id,
                revision_id=revision_id,
            )
            if revision_id is not None and source_revision is not None:
                current_revision = await revision_repository.get_current(
                    document_id, tenant_id
                )
                if (
                    current_revision is not None
                    and current_revision.revision_id != source_revision.revision_id
                ):
                    return {
                        "status": "superseded",
                        "document_id": str(document_id),
                        "revision_id": str(source_revision.revision_id),
                        "current_revision_id": str(current_revision.revision_id),
                    }
        except Exception as error:  # noqa: BLE001 - recorded by the fenced failure path below
            resolution_error = error

        # #711: take processing authority, atomically with the PARSING status.
        # The document row is locked before the authority row, the same order
        # every other writer (reprocess, recovery) uses.
        await repo.update_status(tenant_id, document_id, DocumentStatus.PARSING)
        grant, claim_outcome = await _claim_processing(
            session,
            tenant_id=tenant_id,
            document_id=document_id,
            stage=ProcessingStage.INGESTION,
            revision_id=revision_id,
            generation=generation,
            authority=authority,
        )
        if grant is None:
            await session.rollback()
            logger.info(
                "document_ingestion_not_owned",
                extra={"document_id": str(document_id), "outcome": claim_outcome},
            )
            return {"status": claim_outcome, "document_id": str(document_id)}
        await session.commit()

        heartbeat = asyncio.create_task(_document_processing_heartbeat_loop(authority=grant))
        try:
            if resolution_error is not None:
                raise resolution_error
            with processing_authority.bound_authority(grant):
                return await _ingest_owned(
                    session=session,
                    repo=repo,
                    document=document,
                    tenant_id=tenant_id,
                    document_id=document_id,
                    source_revision=source_revision,
                    grant=grant,
                    entity_extraction=entity_extraction,
                    rag_ingestion=rag_ingestion,
                )
        except ProcessingAuthorityLost as lost:
            await session.rollback()
            return _authority_lost_result(document_id=document_id, grant=grant, error=lost)
        except Exception as error:
            logger.error("Error processing document %s: %s", document_id, error, exc_info=True)
            await session.rollback()
            try:
                await _record_ingestion_failure(
                    session=session,
                    repo=repo,
                    tenant_id=tenant_id,
                    document_id=document_id,
                    grant=grant,
                    source_revision=source_revision,
                    error=error,
                )
            except ProcessingAuthorityLost as lost:
                # The failure belongs to an attempt that no longer owns the
                # document: never mark the new owner's document ERROR.
                await session.rollback()
                return _authority_lost_result(document_id=document_id, grant=grant, error=lost)
            raise
        finally:
            await _stop_processing_heartbeat(heartbeat)


async def _ingest_owned(
    *,
    session: Any,
    repo: SqlAlchemyDocumentRepository,
    document: Any,
    tenant_id: TenantId,
    document_id: UUID,
    source_revision: DocumentRevision | None,
    grant: ProcessingAuthority,
    entity_extraction: DocumentsEntityExtractionService,
    rag_ingestion: SqlAlchemyRagIngestionService,
) -> dict[str, Any]:
    """The owned part of ingestion: compute, stage, then commit once, fenced."""
    storage = build_storage_service()
    file_path = await fetch_source_file(
        storage=storage, document=document, revision=source_revision
    )

    parsed_payload = await file_parser.parse_document_file(document, file_path)
    logger.info("Document parsing successful for document %s.", document_id)

    extraction_summary = await entity_extraction.extract_entities_from_document(
        document=document,
        parsed_payload=parsed_payload,
        tenant_id=tenant_id,
    )

    rag_result = await rag_ingestion.ingest_document_chunks(
        document=document,
        parsed_payload=parsed_payload,
        tenant_id=tenant_id,
        # C3a: chunks are stamped with the pinned revision; readers only serve the
        # trusted-current revision's chunks.
        revision_id=source_revision.revision_id if source_revision else None,
    )

    document.document_metadata = document.document_metadata or {}
    text_blocks = parsed_payload.get("text_blocks", [])
    parsed_text = "\n\n".join(
        block.get("text", "") for block in text_blocks if isinstance(block.get("text"), str)
    ).strip()
    contract_clause_count = 0
    metadata = dict(document.document_metadata or {})
    # #712: a fresh parse pass supersedes whatever the last analysis
    # attempt recorded -- a stale "failed, retry me" flag must not
    # survive a genuine re-upload/reprocess.
    metadata.pop("analysis_last_attempt_incomplete", None)
    # Enum value only -- provider messages can carry credentials and
    # never belong in document metadata. Recorded so an operator (or a
    # retry) can tell "nothing to embed" from "provider misconfigured".
    metadata["rag_ingestion_outcome"] = rag_result.outcome.value
    if parsed_text:
        metadata["parsed_text"] = parsed_text
        # C3a: parsed_text is overwritten per ingestion; the stamp lets readers serve
        # it only while it is the trusted-current revision's text.
        if source_revision is not None:
            metadata["parsed_text_revision_id"] = str(source_revision.revision_id)
        else:
            metadata.pop("parsed_text_revision_id", None)
        if document.document_type == DocumentType.CONTRACT:
            contract_clause_count = await _stage_contract_clauses(
                session,
                repo,
                document=document,
                tenant_id=tenant_id,
                source_revision=source_revision,
                authority_revision_id=grant.revision_id,
                parsed_text=parsed_text,
                parsed_payload=parsed_payload,
            )
            if contract_clause_count:
                metadata["contract_clause_count"] = contract_clause_count
    await repo.update_metadata(tenant_id, document_id, metadata)
    from datetime import UTC, datetime

    await repo.update_status(
        tenant_id,
        document_id,
        DocumentStatus.PARSED_PENDING_ANALYSIS,
        parsed_at=datetime.now(UTC),
    )
    # #711: the single fenced commit. Re-verifies this exact attempt in the
    # SAME transaction as every staged output, then hands the generation
    # over to ANALYSIS. A lost authority raises and nothing is committed.
    await processing_authority.finish_ingestion(session, grant)
    await session.commit()

    if contract_clause_count:
        extraction_summary["contract_clauses"] = contract_clause_count

    processing_details = _build_processing_details(extraction_summary)

    try:
        trigger_use_case = TriggerDocumentAnalysisUseCase(
            document_repository=repo,
        )
        trigger_result = await trigger_use_case.execute(
            tenant_id=tenant_id,
            document_id=document_id,
            generation=grant.generation,
        )
        logger.info(
            "document_analysis_trigger_enqueued",
            extra={
                "document_id": str(document_id),
                "task_id": trigger_result.get("task_id"),
                "task_name": trigger_result.get("task_name"),
                "queue": trigger_result.get("queue"),
            },
        )
    except Exception as trigger_error:
        logger.error(
            "document_analysis_trigger_failed",
            exc_info=True,
            extra={"document_id": str(document_id)},
        )
        _dispatch_failed_task(
            tenant_id=str(tenant_id),
            task_type="document_analysis",
            document_id=str(document_id),
            payload={"document_id": str(document_id)},
            error_message=str(trigger_error),
        )
        await _push_trigger_failure_to_dlq(
            tenant_id=tenant_id,
            document_id=document_id,
            error=trigger_error,
        )

    logger.info(
        "document_ingestion_stop_point_reached",
        extra={
            "document_id": str(document_id),
            "processing_stage": processing_details["processing_stage"],
            "analysis_status": processing_details["analysis_status"],
        },
    )
    return {
        "status": "success",
        "document_id": str(document_id),
        "details": processing_details,
    }


class RevisionAuthorityMismatchError(ValueError):
    """The bytes being ingested are not the revision the processing authority pinned."""


async def _stage_contract_clauses(
    session: Any,
    repo: SqlAlchemyDocumentRepository,
    *,
    document: Any,
    tenant_id: TenantId,
    source_revision: DocumentRevision | None,
    authority_revision_id: UUID | None,
    parsed_text: str,
    parsed_payload: dict[str, Any],
) -> int:
    """Stage the pinned revision's clause rows and its immutable snapshot (C3a).

    Rows are bound to exactly the revision the #711 authority pinned (never the
    latest/current one); a retry or reprocess of that revision reuses its rows,
    and the snapshot is built from the persisted rows so its entity ids are the
    row ids. Returns how many rows were inserted (0 on a replay).
    """
    revision_id = source_revision.revision_id if source_revision is not None else None
    if authority_revision_id is not None and authority_revision_id != revision_id:
        raise RevisionAuthorityMismatchError(
            f"authority pinned revision {authority_revision_id}, ingesting {revision_id}"
        )
    extracted = _extract_contract_clauses(
        document_id=document.id,
        project_id=document.project_id,
        tenant_id=tenant_id,
        parsed_text=parsed_text,
        parsed_payload=parsed_payload,
        revision_id=revision_id,
    )
    event_repository = SqlAlchemyProjectEventRepository(session)
    prior_events = (
        await event_repository.list_for_project(document.project_id, tenant_id)
        if source_revision is not None
        else []
    )
    persisted = await persist_revision_clauses(
        repo,
        tenant_id=tenant_id,
        document_id=document.id,
        revision_id=revision_id,
        extracted=extracted,
        snapshot=(
            snapshot_clauses_for_revision(revision_id, prior_events)
            if revision_id is not None
            else None
        ),
    )
    if source_revision is not None:
        # The events are bound to the immutable revision this task pinned.
        for temporal_event in await build_revision_analysis_events(
            revision=source_revision,
            clauses=list(persisted.clauses),
            existing_events=prior_events,
        ):
            await event_repository.append(temporal_event)
    return persisted.inserted


async def _record_ingestion_failure(
    *,
    session: Any,
    repo: SqlAlchemyDocumentRepository,
    tenant_id: TenantId,
    document_id: UUID,
    grant: ProcessingAuthority,
    source_revision: DocumentRevision | None,
    error: Exception,
) -> None:
    """Fenced failure path: only the current owner may record ERROR.

    Raises ProcessingAuthorityLost when this attempt no longer owns the
    document; then nothing (event, status, lease) is written.
    """
    await processing_authority.verify_in_transaction(session, grant)
    if source_revision is not None:
        # A retry must not hide this failure behind a mutable document status:
        # persist the revision-bound failure projection before re-raising.
        try:
            async with session.begin_nested():
                await SqlAlchemyProjectEventRepository(session).append(
                    build_revision_processing_failed_event(
                        revision=source_revision,
                        failure_code=_temporal_failure_code(error),
                    )
                )
        except Exception as projection_error:  # pragma: no cover - preserves primary failure
            logger.error(
                "temporal_failure_projection_append_failed document_id=%s revision_id=%s error=%s",
                document_id,
                source_revision.revision_id,
                projection_error,
            )
    await repo.update_status(tenant_id, document_id, DocumentStatus.ERROR, parsing_error=str(error))
    # Release the lease (retryable), so Celery's retry can acquire a new fence.
    await processing_authority.settle(
        session, grant, phase=ProcessingPhase.PENDING, outcome="ingestion_failed", error=str(error)
    )
    await session.commit()


def _authority_for_delivery(
    task: Any, authority: dict[str, Any] | None
) -> dict[str, Any] | None:
    """The recovery authority a delivery may adopt, if any.

    #711: the claimed authority is valid for the FIRST execution only. A
    Celery retry (``retries > 0``) is a new attempt after the previous one
    released its lease, so it acquires normally -- acquire never takes over
    from a valid owner. A redelivered copy of the first execution keeps the
    claimed authority and can adopt it at most once.
    """
    retries = int(getattr(getattr(task, "request", None), "retries", 0) or 0)
    return None if retries > 0 else authority


async def _run_document_processing_task_lifecycle(
    *,
    document_id: UUID,
    revision_id: UUID | None,
    generation: int | None = None,
    authority: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    # #711: the heartbeat now starts inside _process, once authority is held.
    return await _process(
        document_id, revision_id, generation=generation, authority=authority
    )


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=True,
    retry_backoff_max=60,
    task_track_started=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_document_async(
    self: Any,
    document_id: str,
    revision_id: str | None = None,
    generation: int | None = None,
    authority: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Asynchronously processes a document using the appropriate parser.

    Args:
        document_id: The unique ID of the document to process. The task
                     retrieves the file path and other info from the database.
        revision_id: The immutable revision to read. Messages without it (legacy
                     producers, reprocess) read the document's current revision.
        generation: #711 processing generation the producer started (reupload /
                    reprocess). A message for an older generation is refused.
        authority: #711 exact authority claimed by the recovery sweep; adopted
                   once, never re-minted by a redelivered copy.
    """
    logger.info(
        "Starting document processing for task_id: %s, document_id: %s, revision_id: %s",
        self.request.id,
        document_id,
        revision_id,
    )
    return run_async_db_task(
        _run_document_processing_task_lifecycle(
            document_id=UUID(document_id),
            revision_id=UUID(revision_id) if revision_id is not None else None,
            generation=generation,
            authority=_authority_for_delivery(self, authority),
        )
    )


async def _close_document_analysis_task_resources(*, primary_error: Exception | None) -> None:
    """Close task-owned async resources before the task event loop terminates."""
    cleanup_error: Exception | None = None
    for resource_name, close_resource in (
        ("checkpointer", close_checkpointer_resources),
        ("database", close_db),
    ):
        try:
            await close_resource()
        except Exception as error:  # pragma: no cover - exercised at runtime boundaries
            logger.exception(
                "document_analysis_task_resource_cleanup_failed",
                extra={"resource": resource_name},
            )
            if cleanup_error is None:
                cleanup_error = error

    if cleanup_error is not None and primary_error is None:
        raise cleanup_error


async def _run_document_analysis_task_lifecycle(
    *,
    tenant_id: TenantId,
    document_id: UUID,
    route_rag_unavailable_to_dlq: bool,
    automatic_retry_available: bool,
    generation: int | None = None,
    authority: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Own every loop-bound analysis resource for one Celery task invocation.

    #711: the lease heartbeat runs inside _run_document_analysis, bound to
    the exact authority it obtained.
    """
    primary_error: Exception | None = None
    try:
        return await _run_document_analysis(
            tenant_id=tenant_id,
            document_id=document_id,
            automatic_retry_available=automatic_retry_available,
            generation=generation,
            authority=authority,
        )
    except AnalysisIncompleteRetryableError as error:
        primary_error = error
        if not automatic_retry_available:
            try:
                await _push_trigger_failure_to_dlq(
                    tenant_id=tenant_id,
                    document_id=document_id,
                    error=error,
                )
            except Exception:
                logger.exception(
                    "document_analysis_final_retry_dlq_persistence_failed",
                    extra={
                        "tenant_id": str(tenant_id),
                        "document_id": str(document_id),
                    },
                )
        raise
    except RagChunksUnavailableError as error:
        if not route_rag_unavailable_to_dlq:
            primary_error = error
            raise

        logger.error(
            "document_analysis_rag_chunks_unavailable",
            extra={"tenant_id": str(tenant_id), "document_id": str(document_id)},
        )
        await _push_trigger_failure_to_dlq(
            tenant_id=tenant_id,
            document_id=document_id,
            error=error,
        )
        return {
            "status": "routed_to_dlq",
            "document_id": str(document_id),
            "reason": "rag_chunks_unavailable",
        }
    except Exception as error:
        primary_error = error
        logger.exception(
            "document_analysis_task_failed",
            extra={"tenant_id": str(tenant_id), "document_id": str(document_id)},
        )
        try:
            await _push_trigger_failure_to_dlq(
                tenant_id=tenant_id,
                document_id=document_id,
                error=error,
            )
        except Exception:
            # The graph/analysis error is the primary outcome; DLQ failure is observable
            # but must not replace it while the task-owned loop is still being unwound.
            logger.exception(
                "document_analysis_failure_dlq_persistence_failed",
                extra={"tenant_id": str(tenant_id), "document_id": str(document_id)},
            )
        raise
    finally:
        await _close_document_analysis_task_resources(primary_error=primary_error)


@celery_app.task(
    name="documents.analyze_document",
    bind=True,
    task_track_started=True,
    queue="document_parsing",
    **ANALYSIS_TASK_RETRY_OPTIONS,
)
def process_document_analysis_async(
    self: Any,
    tenant_id: str,
    document_id: str,
    generation: int | None = None,
    authority: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run full document analysis after parsing; persists via graph N17.

    #711: ``generation`` pins the generation whose ingestion handed over;
    ``authority`` is the exact grant a recovery sweep claimed (adopted once).
    """
    logger.info(
        "Starting document analysis for task_id: %s, document_id: %s",
        self.request.id,
        document_id,
    )
    normalized_tenant_id = require_tenant_id(tenant_id)
    retries = int(getattr(self.request, "retries", 0))
    authority = _authority_for_delivery(self, authority)
    try:
        return asyncio.run(
            _run_document_analysis_task_lifecycle(
                tenant_id=normalized_tenant_id,
                document_id=UUID(document_id),
                route_rag_unavailable_to_dlq=retries >= RAG_READINESS_MAX_RETRIES,
                automatic_retry_available=retries < ANALYSIS_MAX_RETRIES,
                generation=generation,
                authority=authority,
            )
        )
    except RagChunksUnavailableError as error:
        countdown = 2**retries
        logger.warning(
            "document_analysis_rag_chunks_retrying",
            extra={
                "tenant_id": tenant_id,
                "document_id": document_id,
                "task_id": self.request.id,
                "retry": retries + 1,
                "countdown_seconds": countdown,
            },
        )
        raise self.retry(
            exc=error,
            countdown=countdown,
            max_retries=RAG_READINESS_MAX_RETRIES,
        )


process_document_analysis_async.queue = "document_parsing"
process_document_analysis_async.name = "documents.analyze_document"
