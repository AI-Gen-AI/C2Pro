"""Coherence HTTP routes.

Refers to Test Suite ID: TASK-OPS-DOCFLOW-009.
"""

from contextlib import suppress
from datetime import UTC, datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import String, cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import Alert as AlertORM
from src.analysis.adapters.persistence.models import Analysis
from src.analysis.domain.enums import AnalysisStatus
from src.coherence.adapters.persistence.models import CoherenceResultORM
from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.core.database import get_session
from src.core.middleware.feature_flags import require_feature
from src.core.security import security_scheme
from src.documents.adapters.persistence.models import DocumentORM
from src.projects.adapters.persistence.models import ProjectORM

# Import v0.3 graph evaluation
from .budget_clause_builder import build_budget_clauses
from .domain.v2_constants import SCORE_VERSION_V1
from .graph.graph import evaluate_coherence_async
from .graph.state import EvaluationConfig
from .models import Clause, CoherenceResult, DashboardSummary, EnrichedCoherenceResult

# Coherence evaluate router — mounted with api_v1_prefix in main.py
logger = structlog.get_logger()

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
    return {category: None for category in COHERENCE_CATEGORIES}


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


def _build_clause(row: tuple) -> Clause | None:
    clause_id = str(row[0])
    text_value = row[1] or ""
    extracted = row[2] or {}
    doc_id = str(row[3])
    doc_type = row[4] or "unknown"
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


async def _get_persisted_clause_candidates(
    db: AsyncSession,
    project_id: UUID,
    tenant_id: UUID,
    max_chunks: int,
) -> list[Clause]:
    """Load persisted document clauses using category-targeted queries."""
    seen_ids: set[str] = set()
    targeted_clauses: list[Clause] = []

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

    for _category, keywords in _CATEGORY_KEYWORDS.items():
        stmt = text(base_query)
        result = await db.execute(
            stmt,
            {
                "project_id": str(project_id),
                "tenant_id": str(tenant_id),
                "limit": _CLAUSES_PER_CATEGORY,
                "keyword_patterns": [f"%{kw.lower()}%" for kw in keywords],
            },
        )
        for row in result.fetchall():
            cid = str(row[0])
            if cid in seen_ids:
                continue
            clause = _build_clause(row)
            if clause:
                targeted_clauses.append(clause)
                seen_ids.add(cid)

    # Chronological fallback: fill remaining budget so boilerplate is not lost
    remaining = max(0, max_chunks - len(targeted_clauses))
    if remaining > 0:
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
            {"project_id": str(project_id), "tenant_id": str(tenant_id), "limit": remaining + len(seen_ids)},
        )
        for row in fallback_result.fetchall():
            cid = str(row[0])
            if cid in seen_ids:
                continue
            clause = _build_clause(row)
            if clause:
                targeted_clauses.append(clause)
                seen_ids.add(cid)
                remaining -= 1
                if remaining <= 0:
                    break

    return targeted_clauses


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

    # Create evaluation config
    config = EvaluationConfig(
        low_budget_mode=payload.low_budget_mode,
        include_rag_similarity=payload.include_rag_similarity,
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

    # Return diagnostics if requested (Task 7.4)
    if include_diagnostics:
        return enriched_result

    # Otherwise return backward-compatible response (Task 7.3)
    return _convert_enriched_to_coherence_result(enriched_result)


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
    return await evaluate_project_coherence(
        payload=payload,
        include_diagnostics=True,
        db=db,
        current_user=current_user,
    )


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

    if latest_analysis and latest_analysis.alerts_count is not None:
        alert_count = latest_analysis.alerts_count

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

    return _maybe_add_v2_dashboard(summary, project_id, last_updated)


def _maybe_add_v2_dashboard(
    summary: DashboardSummary,
    project_id: UUID,
    last_updated: datetime,
) -> DashboardSummary:
    """Attach additive ECOA v2 dashboard data when enabled; v1 remains fail-closed."""
    try:
        from src.coherence.adapters.v1_to_v2 import adapt_v1_dashboard
        from src.coherence.services.v2.shadow_runner import ShadowRunner
        from src.config import get_settings  # local import to avoid circular deps
        settings = get_settings()
        if getattr(settings, "coherence_v2_enabled", False):
            v2_payload = adapt_v1_dashboard(
                summary.model_dump(),
                project_id=project_id,
                generated_at=last_updated,
            )
            summary = summary.model_copy(update={"categories_v2": v2_payload})

            if getattr(settings, "coherence_v2_shadow_mode", True):
                runner = ShadowRunner()
                delta = runner.compare(summary.model_dump(), v2_payload)
                runner.emit(
                    delta,
                    feature_flag_state={
                        "coherence_v2_enabled": True,
                        "coherence_v2_shadow_mode": True,
                    },
                )
    except (AttributeError, ImportError, RuntimeError, TypeError, ValueError):
        logger.exception("coherence_v2_adapter_failed")

    return summary
