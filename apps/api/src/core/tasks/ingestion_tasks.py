"""
C2Pro - Asynchronous Ingestion Tasks

This module defines Celery tasks related to document ingestion and processing.
These tasks are designed to run in the background, decoupled from the main
API request/response cycle.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text

from src.analysis.factories.orchestrator_factory import AnalysisOrchestratorFactory
from src.core.database import get_raw_session, init_db
from src.core.dlq.dlq_service import DLQService
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
from src.documents.adapters.storage.local_file_storage_service import (
    LocalFileStorageService,
)
from src.documents.application.trigger_document_analysis_use_case import (
    TriggerDocumentAnalysisUseCase,
)
from src.documents.domain.models import Clause, ClauseType, DocumentStatus, DocumentType
from src.procurement.adapters.persistence.bom_repository import SQLAlchemyBOMRepository
from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
from src.procurement.application.use_cases.bom_use_cases import CreateBOMItemUseCase
from src.procurement.application.use_cases.wbs_use_cases import CreateWBSItemUseCase
from src.stakeholders.adapters.persistence.sqlalchemy_stakeholder_repository import (
    SqlAlchemyStakeholderRepository,
)
from src.stakeholders.application.create_stakeholder_use_case import CreateStakeholderUseCase

logger = logging.getLogger(__name__)

RAG_READINESS_MAX_RETRIES = 3


class RagChunksUnavailableError(RuntimeError):
    """TS-UD-OPS-DOCFLOW-B-001: analysis must not run before RAG evidence commits."""

storage = LocalFileStorageService()
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
        r"(?:eur|€)\s*([0-9][0-9\.,]*)|([0-9][0-9\.,]*)\s*(?:eur|€)", text, re.IGNORECASE
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

_CRORE_LAKH_RE = re.compile(r"\s*(crore|cr\.?|lakh|lakhs?|lac)\b", re.IGNORECASE)


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
            r"(?:₹|Rs\.?\s*|INR\s*)([0-9][0-9,\.]*)", window, re.IGNORECASE
        )
        if inr_m:
            raw_num = inr_m.group(1)
            num_end = inr_m.end()
        else:
            bare_m = re.search(r"[^0-9₹]([0-9][0-9,\.]*)", window)
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
        r"₹|Rs\.?\s*[0-9]|\bINR\b|\brupee\b|\bcrore\b|\blakh\b", text, re.IGNORECASE
    ):
        return "INR"
    return "EUR"


def _extract_percentage(text: str) -> float | None:
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%", text)
    if not match:
        return None
    try:
        return float(match.group(1)) / 100.0
    except ValueError:
        return None


def _extract_days(text: str) -> int | None:
    match = re.search(r"([0-9]+)\s*(?:day|days|días)", text, re.IGNORECASE)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _extract_months(text: str) -> int | None:
    match = re.search(r"([0-9]+)\s*(?:month|months|mes|meses)", text, re.IGNORECASE)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


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


def _extract_contract_clauses(
    *,
    document_id: UUID,
    project_id: UUID,
    tenant_id: TenantId,
    parsed_text: str,
) -> list[Clause]:
    segments = [
        segment.strip()
        for segment in re.split(r"(?<=[\.!?])\s+|\n\n+", parsed_text)
        if segment.strip()
    ]
    clauses: list[Clause] = []
    for index, segment in enumerate(segments, start=1):
        if len(segment) < 20:
            continue
        clause_type = _infer_contract_clause_type(segment)
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
                extracted_entities=_build_contract_clause_data(segment, parsed_text),
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


async def _run_document_analysis(
    *,
    tenant_id: TenantId,
    document_id: UUID,
    orchestrator: Any = None,
) -> dict[str, Any]:
    """Run the full analysis graph for a parsed document and persist via N17."""
    await init_db()

    async with get_raw_session() as session:
        repo = SqlAlchemyDocumentRepository(session=session)
        document = await repo.get_by_id(tenant_id, document_id)
        if not document:
            raise ValueError("document not found or access denied")
        if not document.is_parsed():
            raise ValueError("document must be parsed before analysis")

        parsed_text = (
            document.document_metadata.get("parsed_text") if document.document_metadata else None
        )
        if not parsed_text:
            raise ValueError("parsed_text not available")

        chunk_count = await get_document_rag_chunk_count(
            session=session,
            tenant_id=tenant_id,
            document_id=document_id,
        )
        if chunk_count == 0:
            raise RagChunksUnavailableError(
                "RAG chunks were not committed before document analysis"
            )

        graph_orchestrator = orchestrator or AnalysisOrchestratorFactory.create()
        initial_state = {
            "document_text": parsed_text,
            "project_id": str(document.project_id),
            "document_id": str(document.id),
            "doc_type": getattr(document.document_type, "value", "")
            if document.document_type
            else "",
            "tenant_id": str(tenant_id),
            "messages": [],
            "extracted_risks": [],
            "extracted_wbs": [],
            "confidence_score": 0.0,
            "critique_notes": "",
            "human_feedback": "",
            "retry_count": 0,
            "human_approval_required": False,
            "analysis_id": None,
            "force_full_pipeline": True,
        }

        logger.info(
            "document_analysis_task_started",
            extra={"document_id": str(document_id), "tenant_id": str(tenant_id)},
        )
        thread_id = f"document:{document_id}:analysis:{uuid4()}"
        result = await graph_orchestrator.run(initial_state, thread_id=thread_id)
        analysis_id = result.get("analysis_id")
        if analysis_id:
            await repo.update_status(tenant_id, document_id, DocumentStatus.ANALYZED)
            await session.commit()
        logger.info(
            "document_analysis_task_finished",
            extra={
                "document_id": str(document_id),
                "tenant_id": str(tenant_id),
                "analysis_id": analysis_id,
                "persisted": bool(analysis_id),
            },
        )
        return {
            "status": "completed" if analysis_id else "completed_without_persistence",
            "document_id": str(document_id),
            "analysis_id": analysis_id,
            "persisted": bool(analysis_id),
        }


async def _process(document_id: UUID) -> dict[str, Any]:
    """Fetch, parse, update, and trigger analysis for a document."""
    await init_db()

    async with get_raw_session() as session:
        repo = SqlAlchemyDocumentRepository(session=session)

        document = await repo.get_by_id_internal(document_id)
        if not document:
            logger.error("Document with ID '%s' not found. Cannot process.", document_id)
            return {"status": "error", "message": "Document not found"}

        def stakeholder_factory() -> Any:
            stk_repo = SqlAlchemyStakeholderRepository(session=session)
            return CreateStakeholderUseCase(repository=stk_repo, document_repository=repo)

        def wbs_factory() -> Any:
            wbs_repo = SQLAlchemyWBSRepository(session=session)
            return CreateWBSItemUseCase(wbs_repository=wbs_repo)

        def bom_factory() -> Any:
            bom_repo = SQLAlchemyBOMRepository(session=session)
            return CreateBOMItemUseCase(bom_repository=bom_repo)

        if document.created_by is None:
            raise ValueError("document has no created_by user_id")
        entity_extraction = DocumentsEntityExtractionService(
            stakeholder_use_case_factory=stakeholder_factory,
            wbs_use_case_factory=wbs_factory,
            bom_use_case_factory=bom_factory,
            user_id=document.created_by,
        )
        rag_ingestion = SqlAlchemyRagIngestionService(db_session=session)

        raw_tenant_id = await repo.get_project_tenant_id(document.project_id)
        if not raw_tenant_id:
            logger.error("tenant_id_not_found_for_project: project_id=%s", document.project_id)
            return {"status": "error", "message": "Project not found"}
        tenant_id = require_tenant_id(raw_tenant_id)

        await repo.update_status(tenant_id, document_id, DocumentStatus.PARSING)
        await session.commit()

        try:
            file_name = f"{document.id}{Path(document.filename).suffix}"
            file_path = await storage.download_file(file_name)

            parsed_payload = await file_parser.parse_document_file(document, file_path)
            logger.info("Document parsing successful for document %s.", document_id)

            extraction_summary = await entity_extraction.extract_entities_from_document(
                document=document,
                parsed_payload=parsed_payload,
                tenant_id=tenant_id,
            )

            await rag_ingestion.ingest_document_chunks(
                document=document,
                parsed_payload=parsed_payload,
                tenant_id=tenant_id,
            )

            document.document_metadata = document.document_metadata or {}
            text_blocks = parsed_payload.get("text_blocks", [])
            parsed_text = "\n\n".join(
                block.get("text", "") for block in text_blocks if isinstance(block.get("text"), str)
            ).strip()
            contract_clause_count = 0
            metadata = dict(document.document_metadata or {})
            if parsed_text:
                metadata["parsed_text"] = parsed_text
                if document.document_type == DocumentType.CONTRACT:
                    existing_clauses = await repo.list_clauses_for_document(tenant_id, document_id)
                    if not existing_clauses:
                        extracted_clauses = _extract_contract_clauses(
                            document_id=document_id,
                            project_id=document.project_id,
                            tenant_id=tenant_id,
                            parsed_text=parsed_text,
                        )
                        for clause in extracted_clauses:
                            await repo.add_clause(tenant_id, clause)
                        contract_clause_count = len(extracted_clauses)
                        metadata["contract_clause_count"] = contract_clause_count
            await repo.update_metadata(tenant_id, document_id, metadata)
            from datetime import UTC, datetime

            await repo.update_status(
                tenant_id,
                document_id,
                DocumentStatus.PARSED_PENDING_ANALYSIS,
                parsed_at=datetime.now(UTC),
            )
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

        except Exception as error:
            logger.error("Error processing document %s: %s", document_id, error, exc_info=True)
            await session.rollback()
            await repo.update_status(
                tenant_id, document_id, DocumentStatus.ERROR, parsing_error=str(error)
            )
            await session.commit()
            raise


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=True,
    retry_backoff_max=60,
    task_track_started=True,
)
def process_document_async(self: Any, document_id: str) -> dict[str, Any]:
    """
    Asynchronously processes a document using the appropriate parser.

    Args:
        document_id: The unique ID of the document to process. The task
                     retrieves the file path and other info from the database.
    """
    logger.info(
        "Starting document processing for task_id: %s, document_id: %s",
        self.request.id,
        document_id,
    )
    return asyncio.run(_process(UUID(document_id)))


@celery_app.task(
    name="documents.analyze_document",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=True,
    retry_backoff_max=60,
    task_track_started=True,
    queue="document_parsing",
)
def process_document_analysis_async(self: Any, tenant_id: str, document_id: str) -> dict[str, Any]:
    """Run full document analysis after parsing; persists via graph N17."""
    logger.info(
        "Starting document analysis for task_id: %s, document_id: %s",
        self.request.id,
        document_id,
    )
    normalized_tenant_id = require_tenant_id(tenant_id)
    try:
        return asyncio.run(
            _run_document_analysis(
                tenant_id=normalized_tenant_id,
                document_id=UUID(document_id),
            )
        )
    except RagChunksUnavailableError as error:
        retries = int(getattr(self.request, "retries", 0))
        if retries < RAG_READINESS_MAX_RETRIES:
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

        logger.error(
            "document_analysis_rag_chunks_unavailable",
            extra={
                "tenant_id": tenant_id,
                "document_id": document_id,
                "task_id": self.request.id,
            },
        )
        asyncio.run(
            _push_trigger_failure_to_dlq(
                tenant_id=normalized_tenant_id,
                document_id=UUID(document_id),
                error=error,
            )
        )
        return {
            "status": "routed_to_dlq",
            "document_id": document_id,
            "reason": "rag_chunks_unavailable",
        }
    except Exception as error:
        logger.exception(
            "document_analysis_task_failed",
            extra={
                "tenant_id": tenant_id,
                "document_id": document_id,
                "task_id": self.request.id,
            },
        )
        asyncio.run(
            _push_trigger_failure_to_dlq(
                tenant_id=normalized_tenant_id,
                document_id=UUID(document_id),
                error=error,
            )
        )
        raise


process_document_analysis_async.queue = "document_parsing"
process_document_analysis_async.name = "documents.analyze_document"
