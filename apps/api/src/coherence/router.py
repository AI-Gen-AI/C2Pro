"""Coherence HTTP routes.

Refers to Test Suite ID: TASK-OPS-DOCFLOW-009.
"""

from collections.abc import Sequence
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import String, cast, delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.alerts.adapters.persistence.tenant_repository import SqlAlchemyTenantRepository
from src.analysis.adapters.persistence.models import Alert as AlertORM
from src.analysis.adapters.persistence.models import Analysis
from src.analysis.domain.enums import AlertSeverity, AlertType, AnalysisStatus
from src.coherence.adapters.persistence.models import CoherenceResultORM
from src.coherence.feature_flags import (
    coherence_canonical_canary_enabled_for_tenant,
    coherence_llm_crosscheck_enabled_for_tenant,
    coherence_v2_enabled_for_tenant,
)
from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.core.database import get_session
from src.core.feature_flags.tenant_flags_service import TenantFlagsService
from src.core.middleware.feature_flags import require_feature
from src.core.security import security_scheme
from src.documents.adapters.persistence.models import DocumentORM
from src.projects.adapters.persistence.models import ProjectORM

# Import v0.3 graph evaluation
from .budget_clause_builder import build_budget_clauses
from .canonical.live_rescore import (
    CanonicalRescore,
    canonical_category_name,
    canonical_rescore,
)
from .domain.v2_constants import SCORE_VERSION_V1, SCORE_VERSION_V2
from .graph.graph import evaluate_coherence_async
from .graph.state import EvaluationConfig
from .models import Clause, CoherenceResult, DashboardSummary, EnrichedCoherenceResult
from .schedule_clause_builder import build_schedule_clauses

# Coherence evaluate router — mounted with api_v1_prefix in main.py
logger = structlog.get_logger()


def get_flags_service(db: AsyncSession = Depends(get_session)) -> TenantFlagsService:
    """FastAPI dependency: per-request TenantFlagsService backed by the request DB session."""
    from src.config import get_settings  # local import — avoids circular dep

    return TenantFlagsService(
        tenant_repository=SqlAlchemyTenantRepository(db),
        settings=get_settings(),
    )


async def _v2_enabled_for(tenant_id: UUID, flags_service: TenantFlagsService | None) -> bool:
    """Resolve the per-tenant v2 flag, falling back to global settings when DI is unavailable.

    When the endpoint is called directly in tests (outside FastAPI's request cycle),
    ``flags_service`` is the unresolved ``Depends`` sentinel rather than a real service.
    The isinstance guard detects that case and falls back to the same global-settings
    lookup that the code used before TASK-COH-V2-CUTOVER-004.
    """
    if not isinstance(flags_service, TenantFlagsService):
        from src.config import get_settings

        return getattr(get_settings(), "coherence_v2_enabled", False)
    return await coherence_v2_enabled_for_tenant(tenant_id, flags_service=flags_service)

router = APIRouter(
    prefix="/coherence",
    tags=["Coherence Engine"],
    responses={404: {"description": "Not found"}},
    dependencies=[
        Depends(require_feature("feature_coherence_analysis")),
        Depends(security_scheme),
    ],
)

# Coherence dashboard router — mounted with api_v1_prefix in main.py
dashboard_router = APIRouter(
    prefix="/coherence/dashboard",
    tags=["Coherence Dashboard"],
    dependencies=[
        Depends(require_feature("feature_coherence_analysis")),
        Depends(security_scheme),
    ],
)

COHERENCE_CATEGORIES = ("SCOPE", "BUDGET", "QUALITY", "TECHNICAL", "LEGAL", "TIME")
COHERENCE_WEIGHTS = {
    "SCOPE": 0.20,
    "BUDGET": 0.20,
    "QUALITY": 0.15,
    "TECHNICAL": 0.15,
    "LEGAL": 0.15,
    "TIME": 0.15,
}


def _normalize_utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class CoherenceEvaluateRequest(BaseModel):
    """Request model that accepts either project_id (to fetch from RAG) or clauses directly."""

    project_id: UUID | None = Field(
        None,
        description="Project ID to fetch document clauses from RAG. If provided, clauses are auto-fetched.",
    )
    analysis_id: str | None = Field(
        None,
        description="Optional analysis ID for context.",
    )
    clauses: list[Clause] | None = Field(
        None,
        description="Optional explicit clauses. If provided, project_id is ignored.",
    )
    max_chunks: int = Field(
        default=50,
        description="Maximum RAG chunks to fetch for clause extraction.",
    )
    low_budget_mode: bool = Field(
        default=True,
        description="Enable low-budget mode (skip LLM evaluators, default: True)",
    )
    include_rag_similarity: bool = Field(
        default=True,
        description="Enable RAG similarity detection (default: True)",
    )


def _empty_sub_scores() -> dict[str, float | None]:
    return dict.fromkeys(COHERENCE_CATEGORIES)


def _normalized_sub_scores(raw_scores: object) -> dict[str, float | None]:
    normalized = _empty_sub_scores()
    if not raw_scores or not isinstance(raw_scores, dict):
        return normalized

    for category, score in raw_scores.items():
        category_key = str(category).upper()
        if category_key in normalized and score is not None:
            with suppress(TypeError, ValueError):
                normalized[category_key] = float(score)
    return normalized


def _infer_category_from_clause(clause: Clause) -> str:
    """
    Infer category from clause data or metadata (Task 7.2).

    Categories:
    - BUDGET: Has budget/cost/amount/price fields
    - TIME: Has deadline/schedule/date/duration fields
    - LEGAL: Has contract/legal/warranty/notice fields
    - TECHNICAL: Has specification/BOM/material fields
    - QUALITY: Has inspection/standard/quality fields
    - SCOPE: Default for deliverables/scope fields
    """
    data = clause.data
    text_lower = clause.text.lower()

    # Check data fields first
    budget_keywords = {"budget", "cost", "amount", "price", "planned", "current", "total", "payment"}
    time_keywords = {"deadline", "schedule", "date", "duration", "milestone", "end_date", "start_date"}
    legal_keywords = {"contract", "legal", "warranty", "notice", "penalty", "insurance", "term"}
    technical_keywords = {"specification", "bom", "material", "lead_time", "spec", "standard"}
    quality_keywords = {"inspection", "quality", "standard", "testing", "review"}

    if any(key in data for key in budget_keywords):
        return "BUDGET"
    if any(key in data for key in time_keywords):
        return "TIME"
    if any(key in data for key in legal_keywords):
        return "LEGAL"
    if any(key in data for key in technical_keywords):
        return "TECHNICAL"
    if any(key in data for key in quality_keywords):
        return "QUALITY"

    # Fallback: check text content
    if any(keyword in text_lower for keyword in ["budget", "cost", "$", "usd"]):
        return "BUDGET"
    if any(keyword in text_lower for keyword in ["deadline", "schedule", "milestone", "date"]):
        return "TIME"
    if any(keyword in text_lower for keyword in ["contract", "legal", "warranty"]):
        return "LEGAL"
    if any(keyword in text_lower for keyword in ["specification", "material", "bom"]):
        return "TECHNICAL"
    if any(keyword in text_lower for keyword in ["quality", "inspection", "standard"]):
        return "QUALITY"

    # Default to SCOPE
    return "SCOPE"


def _convert_enriched_to_coherence_result(enriched: EnrichedCoherenceResult) -> CoherenceResult:
    """
    Convert EnrichedCoherenceResult to CoherenceResult for backward compatibility (Task 7.3).

    This preserves the existing API contract while using the new scoring engine.
    """
    return CoherenceResult(
        overall_score=enriched.overall_score,
        alerts=enriched.alerts,
        category_breakdown=enriched.category_breakdown,
        calculated_at=enriched.calculated_at,
    )


_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "LEGAL":     ["penalty", "notice", "terminat", "warrant", "liabilit", "indemnif", "arbitrat", "dispute", "insurance"],
    "TIME":      ["completion", "milestone", "delay", "deadline", "schedule", "float", "duration", "commencement"],
    "BUDGET":    ["payment", "price", "invoice", "retention", "advance", "contract sum", "contract price", "lump sum"],
    "TECHNICAL": ["specification", "standard", "iso", "astm", "equipment", "bom", "engineering", "design"],
    "QUALITY":   ["inspection", "test", "commissioning", "defect", "quality", "acceptance"],
    "SCOPE":     ["deliverable", "scope of work", "scope of supply", "shall supply", "shall provide", "shall design"],
}

# Clauses per category on targeted pass; fallback fills remainder up to max_chunks.
_CLAUSES_PER_CATEGORY = 10


def _build_clause(row: Sequence[object]) -> Clause | None:
    clause_id = str(row[0])
    text_value = str(row[1]) if row[1] else ""
    extracted = row[2] or {}
    doc_id = str(row[3])
    doc_type = str(row[4]) if row[4] else "unknown"
    if not text_value:
        return None
    extracted_dict = extracted if isinstance(extracted, dict) else {}
    affected_categories = extracted_dict.get("affected_categories")
    if not isinstance(affected_categories, list) or not affected_categories:
        fallback_category = extracted_dict.get("category", doc_type)
        affected_categories = [str(fallback_category).upper()]
    return Clause(
        id=clause_id,
        text=text_value,
        data={
            "document_id": doc_id,
            "source": "persisted_clause",
            "source_document_type": doc_type,
            "category": affected_categories[0],
            "affected_categories": affected_categories,
            **extracted_dict,
        },
    )


def _append_unique_clause(
    row: Sequence[object],
    clauses: list[Clause],
    seen_ids: set[str],
) -> bool:
    clause_id = str(row[0])
    if clause_id in seen_ids:
        return False
    clause = _build_clause(row)
    if not clause:
        return False
    clauses.append(clause)
    seen_ids.add(clause_id)
    return True


async def get_clauses_from_rag(
    db: AsyncSession,
    project_id: UUID,
    tenant_id: UUID,
    max_chunks: int = 50,
) -> list[Clause]:
    """
    Resolve coherence clauses with this precedence:
    1. Persisted document clauses — category-targeted multi-query
    2. RAG chunks
    3. Parsed document text fallback

    Category-targeted strategy: run one keyword-filtered query per category
    (LEGAL, TIME, BUDGET, TECHNICAL, QUALITY, SCOPE), take up to
    _CLAUSES_PER_CATEGORY hits each, deduplicate, then fill remaining budget
    with a chronological fallback so boilerplate clauses are still present.
    """
    targeted_clauses = await _get_persisted_clause_candidates(
        db, project_id, tenant_id, max_chunks
    )
    targeted_clauses = await _with_budget_clause_candidates(
        targeted_clauses, db, project_id, tenant_id
    )
    targeted_clauses = await _with_schedule_clause_candidates(
        targeted_clauses, db, project_id, tenant_id, max_chunks=max_chunks
    )
    if targeted_clauses:
        return targeted_clauses

    rag_clauses = await _get_rag_chunk_clauses(db, project_id, tenant_id, max_chunks)
    if rag_clauses:
        return rag_clauses

    return await _get_parsed_text_fallback_clauses(db, project_id, tenant_id)


async def _with_budget_clause_candidates(
    clauses: list[Clause],
    db: AsyncSession,
    project_id: UUID,
    tenant_id: UUID,
) -> list[Clause]:
    """Return persisted clauses plus synthetic budget clauses, without duplicate IDs."""
    combined = list(clauses)
    seen_ids = {clause.id for clause in clauses}
    for clause in await build_budget_clauses(db, project_id, tenant_id):
        if clause.id not in seen_ids:
            combined.append(clause)
            seen_ids.add(clause.id)
    return combined


async def _with_schedule_clause_candidates(
    clauses: list[Clause],
    db: AsyncSession,
    project_id: UUID,
    tenant_id: UUID,
    *,
    max_chunks: int,
) -> list[Clause]:
    """Return persisted clauses plus tenant-scoped synthetic schedule clauses."""
    combined = list(clauses)
    seen_ids = {clause.id for clause in clauses}
    for clause in await build_schedule_clauses(
        db,
        project_id,
        tenant_id,
        max_items=max_chunks,
    ):
        if clause.id not in seen_ids:
            combined.append(clause)
            seen_ids.add(clause.id)
    return combined


async def _get_persisted_clause_candidates(
    db: AsyncSession,
    project_id: UUID,
    tenant_id: UUID,
    max_chunks: int,
) -> list[Clause]:
    """Load persisted document clauses using category-targeted queries."""
    seen_ids: set[str] = set()
    base_query = """
        SELECT c.id, c.full_text, c.extracted_entities, d.id, d.document_type::text
        FROM clauses c
        JOIN documents d ON c.document_id = d.id
        JOIN projects p ON d.project_id = p.id
        WHERE d.project_id = CAST(:project_id AS uuid)
          AND p.tenant_id = CAST(:tenant_id AS uuid)
          AND LOWER(c.full_text) LIKE ANY(CAST(:keyword_patterns AS text[]))
        ORDER BY c.created_at ASC
        LIMIT :limit
    """
    targeted_clauses = await _load_category_clause_candidates(
        db, base_query, project_id, tenant_id, seen_ids
    )

    remaining = max(0, max_chunks - len(targeted_clauses))
    if remaining > 0:
        targeted_clauses.extend(
            await _load_fallback_clause_candidates(
                db, project_id, tenant_id, remaining, seen_ids
            )
        )

    return targeted_clauses


async def _load_category_clause_candidates(
    db: AsyncSession,
    base_query: str,
    project_id: UUID,
    tenant_id: UUID,
    seen_ids: set[str],
) -> list[Clause]:
    clauses: list[Clause] = []
    for _category, keywords in _CATEGORY_KEYWORDS.items():
        result = await db.execute(
            text(base_query),
            {
                "project_id": str(project_id),
                "tenant_id": str(tenant_id),
                "limit": _CLAUSES_PER_CATEGORY,
                "keyword_patterns": [f"%{kw.lower()}%" for kw in keywords],
            },
        )
        for row in result.fetchall():
            _append_unique_clause(row, clauses, seen_ids)
    return clauses


async def _load_fallback_clause_candidates(
    db: AsyncSession,
    project_id: UUID,
    tenant_id: UUID,
    remaining: int,
    seen_ids: set[str],
) -> list[Clause]:
    fallback_stmt = text("""
        SELECT c.id, c.full_text, c.extracted_entities, d.id, d.document_type::text
        FROM clauses c
        JOIN documents d ON c.document_id = d.id
        JOIN projects p ON d.project_id = p.id
        WHERE d.project_id = CAST(:project_id AS uuid)
          AND p.tenant_id = CAST(:tenant_id AS uuid)
        ORDER BY c.created_at ASC
        LIMIT :limit
    """)
    fallback_result = await db.execute(
        fallback_stmt,
        {
            "project_id": str(project_id),
            "tenant_id": str(tenant_id),
            "limit": remaining + len(seen_ids),
        },
    )
    clauses: list[Clause] = []
    for row in fallback_result.fetchall():
        if _append_unique_clause(row, clauses, seen_ids) and len(clauses) >= remaining:
            break
    return clauses


async def _get_rag_chunk_clauses(
    db: AsyncSession,
    project_id: UUID,
    tenant_id: UUID,
    max_chunks: int,
) -> list[Clause]:
    """Load RAG chunk fallback clauses."""
    stmt = text("""
        SELECT dc.content, dc.metadata, dc.document_id
        FROM document_chunks dc
        JOIN projects p ON dc.project_id = p.id
        WHERE dc.project_id = CAST(:project_id AS uuid)
          AND p.tenant_id = CAST(:tenant_id AS uuid)
        ORDER BY dc.created_at DESC
        LIMIT :limit
    """)
    result = await db.execute(
        stmt,
        {"project_id": str(project_id), "tenant_id": str(tenant_id), "limit": max_chunks}
    )
    rows = result.fetchall()

    clauses = []
    for i, row in enumerate(rows):
        metadata = row[1] or {}
        doc_id = str(row[2]) if row[2] else str(project_id)
        inferred_category = str(metadata.get("document_type", "unknown")).upper()
        clause = Clause(
            id=f"chunk_{i}_{doc_id[:8]}",
            text=row[0],
            data={
                "document_id": doc_id,
                "source": "rag_chunk",
                "source_document_type": metadata.get("document_type", "unknown"),
                "category": inferred_category,
                "affected_categories": [inferred_category],
            },
        )
        clauses.append(clause)

    return clauses


async def _get_parsed_text_fallback_clauses(
    db: AsyncSession,
    project_id: UUID,
    tenant_id: UUID,
) -> list[Clause]:
    """Load parsed document text fallback clauses."""
    fallback_stmt = text("""
        SELECT d.id, d.document_type::text, d.document_metadata
        FROM documents d
        JOIN projects p ON d.project_id = p.id
        WHERE d.project_id = CAST(:project_id AS uuid)
          AND p.tenant_id = CAST(:tenant_id AS uuid)
          AND d.upload_status IN ('parsed', 'parsed_pending_analysis', 'analyzed')
        ORDER BY d.created_at DESC
    """)
    fallback_result = await db.execute(
        fallback_stmt,
        {"project_id": str(project_id), "tenant_id": str(tenant_id)},
    )
    documents = fallback_result.fetchall()

    fallback_clauses = []
    for row in documents:
        doc_id = str(row[0])
        doc_type = row[1] or "unknown"
        metadata = row[2] or {}
        parsed_text = metadata.get("parsed_text") if isinstance(metadata, dict) else None
        if not isinstance(parsed_text, str) or not parsed_text.strip():
            continue
        normalized_doc_type = str(doc_type).upper()
        fallback_clauses.append(
            Clause(
                id=f"parsed_{doc_id[:8]}",
                text=parsed_text.strip(),
                data={
                    "document_id": doc_id,
                    "source": "document_metadata.parsed_text",
                    "source_document_type": doc_type,
                    "category": normalized_doc_type,
                    "affected_categories": [normalized_doc_type],
                },
            )
        )
    return fallback_clauses


# Map coherence alert severity strings to the alerts-table severity enum.
_COHERENCE_ALERT_SEVERITY: dict[str, AlertSeverity] = {
    "critical": AlertSeverity.CRITICAL,
    "high": AlertSeverity.HIGH,
    "medium": AlertSeverity.MEDIUM,
    "low": AlertSeverity.LOW,
}


async def _mirror_coherence_alerts_to_alerts_table(
    *,
    db: AsyncSession,
    project_id: UUID,
    tenant_id: UUID,
    alerts: Sequence[Any],
) -> None:
    """Mirror ``/evaluate`` coherence alerts into the ``alerts`` table.

    The alerts UI lists rows from the ``alerts`` table (ListAlertsUseCase), but
    ``/evaluate`` only stored alerts inside ``coherence_results.alerts`` (JSON) —
    so the dashboard showed a non-zero ``alert_count`` while the alerts page stayed
    empty. Coherence-sourced rows are ``analysis_id=NULL`` + ``alert_type=COHERENCE``;
    the prior batch for the project is replaced first so re-evaluating never
    duplicates. Not committed here — the caller commits with the coherence result.
    """
    await db.execute(
        delete(AlertORM).where(
            AlertORM.project_id == project_id,
            AlertORM.tenant_id == tenant_id,
            AlertORM.analysis_id.is_(None),
            AlertORM.alert_type == AlertType.COHERENCE,
        )
    )
    for alert in alerts:
        severity_key = str(getattr(alert.severity, "value", alert.severity)).lower()
        message = (alert.message or "Coherence issue detected.").strip()
        evidence = getattr(alert, "evidence", None)
        db.add(
            AlertORM(
                project_id=project_id,
                tenant_id=tenant_id,
                analysis_id=None,
                severity=_COHERENCE_ALERT_SEVERITY.get(severity_key, AlertSeverity.MEDIUM),
                alert_type=AlertType.COHERENCE,
                category=getattr(alert, "category", None),
                rule_id=getattr(alert, "rule_id", None),
                title=message[:255],
                message=message,
                description=message,
                alert_metadata={
                    "source": "coherence_evaluate",
                    "evidence": (
                        {
                            "source_clause_id": evidence.source_clause_id,
                            "claim": evidence.claim,
                            "quote": evidence.quote,
                        }
                        if evidence
                        else None
                    ),
                },
            )
        )


_TECHNICAL_PLIEGO_MARKERS: tuple[str, ...] = (
    "prescripciones técnicas",
    "prescripciones tecnicas",
    "especificaciones técnicas",
    "especificaciones tecnicas",
    "pliego técnico",
    "pliego tecnico",
)


def _technical_specs_referenced(clauses: Sequence[Clause]) -> bool:
    """True if any clause references a separate technical specifications document."""
    return any(
        marker in (clause.text or "").lower()
        for clause in clauses
        for marker in _TECHNICAL_PLIEGO_MARKERS
    )


def _annotate_missing_technical_hint(
    result: EnrichedCoherenceResult, clauses: Sequence[Clause]
) -> None:
    """Append an actionable hint to ``score_reason`` when TECHNICAL is withheld for
    lack of evidence but the documents reference an (unprovided) technical pliego.

    Honest by design: it never invents a technical score — it explains the
    withholding and tells the user which document to upload.
    """
    if "TECHNICAL" not in (result.score_missing_dimensions or []):
        return
    if not _technical_specs_referenced(clauses):
        return
    hint = (
        "Technical dimension withheld: the documents reference a technical "
        "specifications pliego (prescripciones técnicas) that was not provided. "
        "Upload the Pliego de prescripciones técnicas for a technical coherence score."
    )
    result.score_reason = (
        f"{result.score_reason} {hint}".strip() if result.score_reason else hint
    )


# ---- API Endpoint ----
@router.post(
    "/evaluate",
    response_model=CoherenceResult,
    summary="Evaluate Project Coherence",
    description="""
    Accepts a project's context and evaluates it against a predefined set of coherence rules.
    Returns a list of alerts and a calculated coherence score.

    Can work in two modes:
    1. With project_id: Fetches document clauses from RAG automatically
    2. With explicit clauses: Uses the provided clauses directly

    **v0.3 Features:**
    - Granular scoring (5-97 range) instead of binary 0/100
    - 27 deterministic evaluators across 6 categories + CROSS
    - Optional LLM semantic evaluation (disabled in low_budget_mode)
    - Optional RAG similarity detection for cross-document analysis
    - Add ?include_diagnostics=true to get detailed diagnostic information
    """,
)
async def evaluate_project_coherence(
    payload: CoherenceEvaluateRequest,
    include_diagnostics: bool = Query(
        default=False,
        description="Include detailed diagnostics in response",
    ),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    flags_service: TenantFlagsService = Depends(get_flags_service),
) -> CoherenceResult | EnrichedCoherenceResult:
    """
    Evaluates the coherence of a project based on its context using v0.3 scoring engine.

    TASK-REV-004: Added current_user for tenant isolation.

    - **payload**: Contains project_id (to fetch from RAG) OR explicit clauses
    - **include_diagnostics**: If True, returns EnrichedCoherenceResult with diagnostics

    Returns the evaluation result, including alerts and a granular score (5-97 range).
    """
    # Determine clauses source
    if payload.clauses:
        clauses = payload.clauses
    elif payload.project_id:
        clauses = await get_clauses_from_rag(
            db, payload.project_id, current_user.tenant_id, payload.max_chunks
        )
        if not clauses:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No document clauses found. Please upload and parse documents first.",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either project_id or clauses must be provided.",
        )

    logger.info(
        "coherence_evaluate_start",
        clauses_count=len(clauses),
        low_budget_mode=payload.low_budget_mode,
        include_rag_similarity=payload.include_rag_similarity,
        include_diagnostics=include_diagnostics,
    )

    # Resolve the LLM cross-clause depth flag per tenant (default off). Adds a bounded LLM
    # call to detect semantic contradictions between clause pairs; the deterministic floor
    # is always on regardless. Resolved here so the graph node stays free of the flags service.
    llm_crosscheck_enabled = False
    if flags_service is not None:
        try:
            llm_crosscheck_enabled = await coherence_llm_crosscheck_enabled_for_tenant(
                current_user.tenant_id, flags_service=flags_service
            )
        except Exception:
            logger.warning("coherence_llm_crosscheck_flag_resolution_failed", exc_info=True)

    # Create evaluation config
    config = EvaluationConfig(
        low_budget_mode=payload.low_budget_mode,
        include_rag_similarity=payload.include_rag_similarity,
        llm_crosscheck_enabled=llm_crosscheck_enabled,
        tenant_id=str(current_user.tenant_id),
        project_id=str(payload.project_id) if payload.project_id else None,
    )

    # Evaluate using LangGraph subgraph
    enriched_result = await evaluate_coherence_async(
        clauses=clauses,
        project_id=str(payload.project_id) if payload.project_id else "manual",
        config=config,
    )

    logger.info(
        "coherence_evaluate_complete",
        alerts_count=len(enriched_result.alerts),
        overall_score=enriched_result.overall_score,
    )

    # Referenced-but-missing hint: if the technical dimension was withheld for lack
    # of evidence but the documents reference a technical specifications pliego, tell
    # the user what to upload — honest and actionable, never a fabricated score.
    _annotate_missing_technical_hint(enriched_result, clauses)

    # ADR-017 canary: for enrolled tenants, re-score the SAME findings through the canonical
    # scorer (ADR-009 §G.1) — this flips the SCORER only; detection/alerts are unchanged.
    # Always logs the v1↔canonical delta; substitutes the headline only when the tenant is
    # enrolled. Default off (no tenant enrolled) ⇒ persistence + response below are
    # byte-identical to the v1 path.
    enriched_result = await _maybe_apply_canonical_canary(
        enriched_result, tenant_id=current_user.tenant_id, flags_service=flags_service
    )

    # Persist result so the dashboard always reflects the latest evaluation
    if payload.project_id and enriched_result.overall_score is not None:
        # Normalize legacy "SCHEDULE"→"TIME" so dashboard sub_scores keys match COHERENCE_CATEGORIES
        _CAT_ALIAS = {"SCHEDULE": "TIME", "FINANCIAL": "BUDGET", "GENERAL": "SCOPE"}

        def _norm_cat(cat: str) -> str:
            key = cat.upper()
            return _CAT_ALIAS.get(key, key)

        category_scores = {
            _norm_cat(item.category): item.score
            for item in enriched_result.category_breakdown
        }
        category_details = [
            {
                "category": _norm_cat(item.category),
                "score": item.score,
                "alert_count": item.alert_count,
                "severity_breakdown": dict(item.severity_breakdown) if item.severity_breakdown else {},
                "impact_percentage": item.impact_percentage,
            }
            for item in enriched_result.category_breakdown
        ]
        alerts_data = [
            {
                "rule_id": a.rule_id,
                "severity": a.severity,
                "category": a.category,
                "message": a.message,
                "evidence": (
                    {
                        "source_clause_id": a.evidence.source_clause_id,
                        "claim": a.evidence.claim,
                        "quote": a.evidence.quote,
                    }
                    if a.evidence
                    else None
                ),
            }
            for a in enriched_result.alerts
        ]
        db.add(
            CoherenceResultORM(
                project_id=payload.project_id,
                tenant_id=current_user.tenant_id,
                global_score=round(enriched_result.overall_score),
                category_scores=category_scores,
                category_details=category_details,
                alerts=alerts_data,
                score_version=enriched_result.score_version or SCORE_VERSION_V1,
                score_reason=enriched_result.score_reason,
                score_missing_dimensions=enriched_result.score_missing_dimensions,
            )
        )
        await db.commit()
        # Best-effort: mirror alerts into the alerts table so the alerts UI (which
        # lists the alerts table, not coherence_results.alerts) surfaces them. Runs
        # after the coherence result is committed so a mirroring failure can never
        # fail the already-persisted evaluation.
        try:
            await _mirror_coherence_alerts_to_alerts_table(
                db=db,
                project_id=payload.project_id,
                tenant_id=current_user.tenant_id,
                alerts=enriched_result.alerts,
            )
            await db.commit()
        except Exception:
            logger.warning(
                "coherence_alert_mirror_failed",
                project_id=str(payload.project_id),
                exc_info=True,
            )

    # V2 shadow: run real CoherenceV2Orchestrator and emit delta event.
    # Guard mirrors _maybe_add_v2_dashboard: only fires when both flags are True.
    # Never raises — failures are caught so the V1 response is unaffected.
    # TASK-COH-V2-WIRE-ORCHESTRATOR
    if payload.project_id:
        from src.config import get_settings  # local import — avoids circular dep
        _settings = get_settings()
        if (
            await _v2_enabled_for(current_user.tenant_id, flags_service)
            and getattr(_settings, "coherence_v2_shadow_mode", True)
        ):
            await _run_v2_shadow_on_evaluate(
                v1_result=enriched_result,
                project_id=payload.project_id,
                tenant_id=current_user.tenant_id,
                db=db,
            )

    # Return diagnostics if requested (Task 7.4)
    if include_diagnostics:
        return enriched_result

    # Otherwise return backward-compatible response (Task 7.3)
    return _convert_enriched_to_coherence_result(enriched_result)


async def _maybe_apply_canonical_canary(
    result: EnrichedCoherenceResult,
    *,
    tenant_id: UUID,
    flags_service: TenantFlagsService | None,
) -> EnrichedCoherenceResult:
    """ADR-017 canary: re-score findings via the canonical scorer for enrolled tenants.

    Always emits the v1↔canonical delta (shadow signal). Substitutes the headline only when
    the tenant is enrolled AND the canonical scorer yields a score. Never raises — any
    failure falls back to the untouched v1 result so the canary can't break ``/evaluate``.
    """
    if result.overall_score is None or flags_service is None:
        return result
    try:
        enrolled = await coherence_canonical_canary_enabled_for_tenant(
            tenant_id, flags_service=flags_service
        )
        rescore = canonical_rescore(result.category_breakdown)
    except Exception:
        logger.warning("coherence_canary_rescore_failed", exc_info=True)
        return result

    delta = rescore.score - result.overall_score if rescore.score is not None else None
    logger.info(
        "coherence_canary_rescore",
        tenant_id=str(tenant_id),
        enrolled=enrolled,
        v1_score=result.overall_score,
        canonical_score=rescore.score,
        delta=delta,
    )
    if not enrolled or rescore.score is None:
        return result
    return _apply_canonical_rescore(result, rescore)


def _apply_canonical_rescore(
    result: EnrichedCoherenceResult, rescore: CanonicalRescore
) -> EnrichedCoherenceResult:
    """Return a copy carrying the canonical headline + per-category scores + v2 stamp."""
    updated_breakdown = [
        breakdown.model_copy(
            update={
                "score": rescore.category_scores.get(
                    canonical_category_name(str(breakdown.category)), breakdown.score
                )
            }
        )
        for breakdown in result.category_breakdown
    ]
    return result.model_copy(
        update={
            "overall_score": rescore.score,
            "category_breakdown": updated_breakdown,
            "score_version": SCORE_VERSION_V2,
            "score_reason": rescore.reason or "canonical_canary",
        }
    )


async def _run_v2_shadow_on_evaluate(
    v1_result: EnrichedCoherenceResult,
    project_id: UUID,
    tenant_id: UUID,
    db: AsyncSession,
) -> None:
    """Run the real CoherenceV2Orchestrator in shadow mode (TASK-COH-V2-WIRE-ORCHESTRATOR).

    Fetches project document metadata (tenant-safe, no text/PII), runs the v2
    orchestrator, and emits a coherence.v1_v2_score_delta structlog event so the
    shadow path carries real bottom-up v2 scores instead of the v1-translation
    from adapt_v1_dashboard.

    Deterministic ConflictService candidates are already carried through the
    v2 orchestrator; this path does not use LLM inference.
    """
    try:
        # ``SET LOCAL`` from the primary v1 request is cleared by its explicit
        # commit above. Re-establish it for the shadow transaction before any
        # tenant-scoped read or forced-RLS v2 insert. Parameter binding keeps
        # the UUID out of SQL construction.
        await db.execute(
            text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )
        from src.coherence.services.v2.aggregator_v2 import GlobalAggregatorV2
        from src.coherence.services.v2.category_aggregator import CategoryAggregator
        from src.coherence.services.v2.conflict_service import (
            ConflictCandidate,
            ConflictService,
            build_conflict_candidates,
        )
        from src.coherence.services.v2.evidence_service import EvidenceService
        from src.coherence.services.v2.orchestrator import (
            CoherenceV2Orchestrator,
            ProjectEvidenceInputs,
        )
        from src.coherence.services.v2.shadow_runner import ShadowRunner
        from src.documents.adapters.persistence.sqlalchemy_document_repository import (
            SqlAlchemyDocumentRepository,
        )

        # Fetch domain Document objects via the RLS-safe repository (double-filters
        # on project_id + tenant_id). limit=200 is a practical ceiling; truncation
        # risk is low for typical projects but noted here as a known limitation.
        doc_repo = SqlAlchemyDocumentRepository(session=db)
        project_docs, _ = await doc_repo.list_for_project(
            tenant_id=tenant_id,
            project_id=project_id,
            skip=0,
            limit=200,
        )

        orchestrator = CoherenceV2Orchestrator(
            evidence=EvidenceService(),
            conflict=ConflictService(),
            cat_agg=CategoryAggregator(),
            global_agg=GlobalAggregatorV2(),
        )
        conflict_candidates_by_category: dict[str, list[ConflictCandidate]] = {}
        for candidate in build_conflict_candidates(v1_result.finding_signals):
            conflict_candidates_by_category.setdefault(candidate.category, []).append(candidate)
        v2_payload = await orchestrator.run(
            project_id=project_id,
            evidence_inputs=ProjectEvidenceInputs(
                project_docs=project_docs,
                project_context={},
                conflict_candidates_by_category=conflict_candidates_by_category,
            ),
        )

        v1_dict: dict[str, object] = {
            "coherence_score": v1_result.overall_score,
            "project_id": str(project_id),
            "tenant_id": str(tenant_id),
            "analysis_id": None,
        }
        runner = ShadowRunner()
        delta = runner.compare(v1_dict, v2_payload)
        runner.emit(
            delta,
            feature_flag_state={
                "coherence_v2_enabled": True,
                "coherence_v2_shadow_mode": True,
            },
        )
        await runner.persist(db=db, tenant_id=tenant_id, v2=v2_payload)
    except Exception:
        # The v1 write was committed before entering shadow mode.  Roll back
        # only the failed shadow transaction so the primary response remains
        # available and this session can complete cleanly.
        with suppress(Exception):
            await db.rollback()
        # Observability failures (including a local console encoder failure)
        # must not turn a best-effort shadow failure into a v1 API failure.
        with suppress(Exception):
            logger.exception("coherence_v2_shadow_evaluate_failed")


# Optional diagnostics endpoint (Task 7.4)
@router.post(
    "/evaluate/diagnostics",
    response_model=EnrichedCoherenceResult,
    summary="Evaluate with Full Diagnostics",
    description="""
    Same as /evaluate but always returns full diagnostic information.

    Includes:
    - finding_signals: All deterministic + LLM signals with impact scores
    - diagnostics: Detailed breakdown of scoring logic
    - cross_pairs: RAG-detected cross-document relationships
    - cost_usd: LLM API cost (if LLM evaluation was enabled)
    """,
)
async def evaluate_with_diagnostics(
    payload: CoherenceEvaluateRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> EnrichedCoherenceResult:
    """
    Evaluate project coherence with full diagnostic output.

    This is a convenience endpoint equivalent to POST /evaluate?include_diagnostics=true
    """
    result = await evaluate_project_coherence(
        payload=payload,
        include_diagnostics=True,
        db=db,
        current_user=current_user,
    )
    if not isinstance(result, EnrichedCoherenceResult):
        # include_diagnostics=True always yields the enriched variant; anything
        # else would fail this route's response_model, so fail loudly here.
        raise HTTPException(status_code=500, detail="Diagnostics result unavailable")
    return result


# ======================================================================
# COHERENCE DASHBOARD ENDPOINT (for TS-E2E-FLW-DOC-001)
# GREEN PHASE: Minimal "Fake It" implementation
# ======================================================================


@dashboard_router.get(
    "/{project_id}",
    response_model=DashboardSummary,
    summary="Get Coherence Dashboard",
    description="""
    Returns coherence dashboard data for a project.
    Derived from the latest Analysis or CoherenceResult records.
    """,
)
async def get_coherence_dashboard(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
    flags_service: TenantFlagsService = Depends(get_flags_service),
) -> DashboardSummary:
    """
    Get coherence dashboard for project.
    Prioritizes the latest completed Analysis, then falls back to CoherenceResult,
    and finally to Project baseline data.
    """
    tenant_id = current_user.tenant_id

    # 1. Fetch Project data
    project_result = await db.execute(
        select(
            ProjectORM.id,
            ProjectORM.tenant_id,
            ProjectORM.coherence_score,
            ProjectORM.last_analysis_at,
            ProjectORM.updated_at,
        ).where(
            ProjectORM.id == project_id,
            ProjectORM.tenant_id == tenant_id,
        )
    )
    project = project_result.one_or_none()

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # 2. Optimized counts and latest timestamps
    document_count_result = await db.execute(
        select(func.count(DocumentORM.id))
        .where(DocumentORM.project_id == project_id)
    )
    document_count = document_count_result.scalar() or 0

    alert_count_result = await db.execute(
        select(func.count(AlertORM.id))
        .where(AlertORM.project_id == project_id)
    )
    alert_count = alert_count_result.scalar() or 0

    # Fetch latest completed analysis
    latest_analysis_result = await db.execute(
        select(
            Analysis.coherence_score,
            Analysis.coherence_breakdown,
            Analysis.alerts_count,
            Analysis.completed_at,
            Analysis.updated_at,
        )
        .where(
            Analysis.project_id == project_id,
            cast(Analysis.status, String).ilike(AnalysisStatus.COMPLETED.value),
        )
        .order_by(Analysis.completed_at.desc().nullslast(), Analysis.created_at.desc())
        .limit(1)
    )
    latest_analysis = latest_analysis_result.one_or_none()

    # Fetch latest coherence result
    coherence_result_data = await db.execute(
        select(
            CoherenceResultORM.global_score,
            CoherenceResultORM.category_scores,
            CoherenceResultORM.alerts,
            CoherenceResultORM.calculated_at,
            CoherenceResultORM.score_version,
            CoherenceResultORM.score_reason,
            CoherenceResultORM.score_missing_dimensions,
        )
        .where(CoherenceResultORM.project_id == project_id)
        .order_by(CoherenceResultORM.calculated_at.desc())
        .limit(1)
    )
    coherence_result = coherence_result_data.one_or_none()

    # Fetch latest metadata for last_updated
    latest_doc_at_result = await db.execute(
        select(func.max(DocumentORM.updated_at))
        .where(DocumentORM.project_id == project_id)
    )
    latest_doc_at = latest_doc_at_result.scalar()

    latest_alert_at_result = await db.execute(
        select(func.max(AlertORM.updated_at))
        .where(AlertORM.project_id == project_id)
    )
    latest_alert_at = latest_alert_at_result.scalar()

    # Determine global score and breakdown
    sub_scores = _empty_sub_scores()
    global_score: float | None = None

    if latest_analysis and latest_analysis.coherence_score is not None:
        global_score = latest_analysis.coherence_score
        sub_scores = _normalized_sub_scores(latest_analysis.coherence_breakdown)
    elif coherence_result:
        global_score = coherence_result.global_score
        sub_scores = _normalized_sub_scores(coherence_result.category_scores)
    elif project.coherence_score is not None:
        global_score = float(project.coherence_score)

    # alert_count follows the same source priority as the score (see docstring):
    # a completed Analysis first, then the latest /evaluate CoherenceResult, else
    # the alerts table count computed above. Without this fallback an evaluate-only
    # project (no analysis pipeline run) always reported alert_count = 0.
    if latest_analysis and latest_analysis.alerts_count is not None:
        alert_count = latest_analysis.alerts_count
    elif coherence_result is not None and coherence_result.alerts is not None:
        alert_count = len(coherence_result.alerts)

    # Calculate last_updated timestamp
    candidates = [
        latest_analysis.completed_at if latest_analysis else None,
        latest_analysis.updated_at if latest_analysis else None,
        coherence_result.calculated_at if coherence_result else None,
        project.last_analysis_at,
        latest_doc_at,
        latest_alert_at,
        project.updated_at,
    ]
    normalized_candidates = [
        normalized
        for candidate in candidates
        if (normalized := _normalize_utc_datetime(candidate)) is not None
    ]
    last_updated = max(normalized_candidates, default=datetime.now(UTC))

    summary = DashboardSummary(
        project_id=str(project_id),
        tenant_id=str(tenant_id),
        global_score=global_score,
        coherence_score=global_score,
        sub_scores=sub_scores,
        weights_used=COHERENCE_WEIGHTS,
        alert_count=alert_count,
        document_count=document_count,
        methodology_version="3.0",
        score_version=coherence_result.score_version if coherence_result else None,
        score_reason=coherence_result.score_reason if coherence_result else None,
        score_missing_dimensions=(
            coherence_result.score_missing_dimensions if coherence_result else None
        ),
        last_updated=last_updated,
        categories_v2=None,
    )

    v2_enabled = await _v2_enabled_for(tenant_id, flags_service)
    return await _maybe_add_v2_dashboard(
        summary, project_id, last_updated, v2_enabled=v2_enabled, db=db
    )


async def _maybe_add_v2_dashboard(
    summary: DashboardSummary,
    project_id: UUID,
    last_updated: datetime,
    *,
    v2_enabled: bool,
    db: AsyncSession,
) -> DashboardSummary:
    """Attach additive ECOA v2 dashboard data when enabled; v1 remains fail-closed.

    Resolution order (when v2_enabled=True):
    1. Latest row in ``coherence_v2_shadow`` — real orchestrator output.
    2. ``adapt_v1_dashboard()`` fallback when no shadow row exists yet.
    """
    try:
        if v2_enabled:
            from src.coherence.adapters.persistence.models import CoherenceV2ShadowORM
            from src.coherence.application.dtos.coherence_v2_dtos import (
                CategoryV2,
                CoherenceV2Payload,
                GlobalV2,
            )

            shadow_row = (
                await db.execute(
                    select(CoherenceV2ShadowORM)
                    .where(CoherenceV2ShadowORM.project_id == project_id)
                    .order_by(CoherenceV2ShadowORM.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()

            if shadow_row is not None:
                # Real evidence-based v2 data from the shadow orchestrator.
                # Cast status str→Literal: the ORM column is str, but values are
                # always written by CoherenceV2Payload which enforces the Literal.
                from typing import Literal
                from typing import cast as _cast

                _GlobalV2Status = Literal[
                    "scored", "partial", "insufficient_active_weight", "pending_documents"
                ]
                v2_payload = CoherenceV2Payload(
                    project_id=project_id,
                    version="coherence-v2",
                    generated_at=shadow_row.created_at,
                    **{
                        "global": GlobalV2(
                            coherence_score=shadow_row.coherence_score,
                            completeness_score=shadow_row.completeness_score,
                            technical_reliability_index=shadow_row.technical_reliability_index,
                            status=_cast(_GlobalV2Status, shadow_row.status),
                            score_reason=shadow_row.score_reason,
                            active_weight=shadow_row.active_weight,
                        )
                    },
                    categories=[CategoryV2(**cat) for cat in shadow_row.categories_v2],
                )
                logger.info(
                    "coherence_v2_dashboard_from_shadow",
                    project_id=str(project_id),
                    shadow_id=str(shadow_row.id),
                    status=shadow_row.status,
                )
            else:
                from src.coherence.adapters.v1_to_v2 import adapt_v1_dashboard

                v2_payload = adapt_v1_dashboard(
                    summary.model_dump(),
                    project_id=project_id,
                    generated_at=last_updated,
                )
                logger.debug(
                    "coherence_v2_dashboard_adapted_from_v1",
                    project_id=str(project_id),
                )

            summary = summary.model_copy(update={"categories_v2": v2_payload})
    except (AttributeError, ImportError, RuntimeError, TypeError, ValueError):
        logger.exception("coherence_v2_adapter_failed")

    return summary
