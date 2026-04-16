# apps/api/src/coherence/router.py
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import String, cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import Alert as AlertORM
from src.analysis.adapters.persistence.models import Analysis
from src.analysis.domain.enums import AnalysisStatus
from src.coherence.adapters.persistence.models import CoherenceResultORM
from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.core.database import get_session, get_session_with_tenant
from src.core.middleware.feature_flags import require_feature
from src.core.security import security_scheme
from src.documents.adapters.persistence.models import DocumentORM
from src.projects.adapters.persistence.models import ProjectORM

# Import v0.3 graph evaluation
from .graph.graph import evaluate_coherence
from .graph.state import EvaluationConfig
from .models import Clause, CoherenceResult, EnrichedCoherenceResult

# Coherence evaluate router — mounted with api_v1_prefix in main.py
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


def _zeroed_sub_scores() -> dict[str, int]:
    return {category: 0 for category in COHERENCE_CATEGORIES}


def _normalized_sub_scores(raw_scores: object) -> dict[str, int]:
    normalized = _zeroed_sub_scores()
    if not raw_scores or not isinstance(raw_scores, dict):
        return normalized

    for category, score in raw_scores.items():
        category_key = str(category).upper()
        if category_key in normalized and score is not None:
            try:
                normalized[category_key] = int(score)
            except (TypeError, ValueError):
                normalized[category_key] = 0
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


async def get_clauses_from_rag(
    db: AsyncSession,
    project_id: UUID,
    tenant_id: UUID,
    max_chunks: int = 50,
) -> list[Clause]:
    """
    Resolve coherence clauses with this precedence:
    1. Persisted document clauses
    2. RAG chunks
    3. Parsed document text fallback
    """
    persisted_stmt = text("""
        SELECT c.id, c.full_text, c.extracted_entities, d.id, d.document_type::text
        FROM clauses c
        JOIN documents d ON c.document_id = d.id
        JOIN projects p ON d.project_id = p.id
        WHERE d.project_id = CAST(:project_id AS uuid)
          AND p.tenant_id = CAST(:tenant_id AS uuid)
        ORDER BY c.created_at ASC
        LIMIT :limit
    """)
    persisted_result = await db.execute(
        persisted_stmt,
        {"project_id": str(project_id), "tenant_id": str(tenant_id), "limit": max_chunks},
    )
    persisted_rows = persisted_result.fetchall()
    persisted_clauses = []
    for row in persisted_rows:
        clause_id = str(row[0])
        text_value = row[1] or ""
        extracted = row[2] or {}
        doc_id = str(row[3])
        doc_type = row[4] or "unknown"
        if not text_value:
            continue
        extracted_dict = extracted if isinstance(extracted, dict) else {}
        affected_categories = extracted_dict.get("affected_categories")
        if not isinstance(affected_categories, list) or not affected_categories:
            fallback_category = extracted_dict.get("category", doc_type)
            affected_categories = [str(fallback_category).upper()]
        persisted_clauses.append(
            Clause(
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
        )
    if persisted_clauses:
        return persisted_clauses

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

    if clauses:
        return clauses

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
    import structlog
    logger = structlog.get_logger()

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
    )

    # Evaluate using LangGraph subgraph
    enriched_result = evaluate_coherence(
        clauses=clauses,
        project_id=str(payload.project_id) if payload.project_id else "manual",
        config=config,
    )

    logger.info(
        "coherence_evaluate_complete",
        alerts_count=len(enriched_result.alerts),
        overall_score=enriched_result.overall_score,
    )

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
) -> EnrichedCoherenceResult:
    """
    Evaluate project coherence with full diagnostic output.

    This is a convenience endpoint equivalent to POST /evaluate?include_diagnostics=true
    """
    # Reuse main endpoint logic with diagnostics forced
    return await evaluate_project_coherence(
        payload=payload,
        include_diagnostics=True,
        db=db,
    )


# ======================================================================
# COHERENCE DASHBOARD ENDPOINT (for TS-E2E-FLW-DOC-001)
# GREEN PHASE: Minimal "Fake It" implementation
# ======================================================================


@dashboard_router.get(
    "/{project_id}",
    summary="Get Coherence Dashboard",
    description="""
    Returns coherence dashboard data for a project.
    Derived from the latest Analysis or CoherenceResult records.
    """,
)
async def get_coherence_dashboard(
    project_id: UUID,
    request: Request,
) -> dict:
    """
    Get coherence dashboard for project.
    Prioritizes the latest completed Analysis, then falls back to CoherenceResult,
    and finally to Project baseline data.
    """
    if not hasattr(request.state, "tenant_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    tenant_id = request.state.tenant_id

    async with get_session_with_tenant(tenant_id) as session:
        project_result = await session.execute(
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

        # Get counts
        document_count = (
            await session.execute(
                select(func.count())
                .select_from(DocumentORM)
                .join(ProjectORM, ProjectORM.id == DocumentORM.project_id)
                .where(
                    DocumentORM.project_id == project_id,
                    ProjectORM.tenant_id == tenant_id,
                )
            )
        ).scalar_one()

        alert_count = (
            await session.execute(
                select(func.count())
                .select_from(AlertORM)
                .join(ProjectORM, ProjectORM.id == AlertORM.project_id)
                .where(
                    AlertORM.project_id == project_id,
                    ProjectORM.tenant_id == tenant_id,
                )
            )
        ).scalar_one()

        # Fetch latest completed analysis without loading enum-bound ORM instances.
        latest_analysis = (
            await session.execute(
                select(
                    Analysis.coherence_score,
                    Analysis.coherence_breakdown,
                    Analysis.alerts_count,
                    Analysis.completed_at,
                    Analysis.updated_at,
                )
                .where(
                    Analysis.project_id == project_id,
                    cast(Analysis.status, String) == AnalysisStatus.COMPLETED.value,
                )
                .order_by(Analysis.completed_at.desc().nullslast(), Analysis.created_at.desc())
                .limit(1)
            )
        ).one_or_none()

        # Fetch latest coherence result (legacy or direct engine output)
        coherence_result = (
            await session.execute(
                select(
                    CoherenceResultORM.global_score,
                    CoherenceResultORM.category_scores,
                    CoherenceResultORM.calculated_at,
                )
                .where(CoherenceResultORM.project_id == project_id)
                .order_by(CoherenceResultORM.calculated_at.desc())
                .limit(1)
            )
        ).one_or_none()

        # Fetch latest metadata for last_updated
        latest_doc_at = (
            await session.execute(
                select(func.max(DocumentORM.updated_at))
                .join(ProjectORM, ProjectORM.id == DocumentORM.project_id)
                .where(
                    DocumentORM.project_id == project_id,
                    ProjectORM.tenant_id == tenant_id,
                )
            )
        ).scalar_one()

        latest_alert_at = (
            await session.execute(
                select(func.max(AlertORM.updated_at))
                .join(ProjectORM, ProjectORM.id == AlertORM.project_id)
                .where(
                    AlertORM.project_id == project_id,
                    ProjectORM.tenant_id == tenant_id,
                )
            )
        ).scalar_one()

    # Determine global score and breakdown
    sub_scores = _zeroed_sub_scores()
    global_score = 0

    if latest_analysis and latest_analysis.coherence_score is not None:
        global_score = latest_analysis.coherence_score
        sub_scores = _normalized_sub_scores(latest_analysis.coherence_breakdown)
    elif coherence_result:
        global_score = coherence_result.global_score
        sub_scores = _normalized_sub_scores(coherence_result.category_scores)
    elif project.coherence_score is not None:
        global_score = int(project.coherence_score)

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

    return {
        "project_id": str(project_id),
        "tenant_id": str(tenant_id),
        "global_score": global_score,
        "coherence_score": global_score,
        "sub_scores": sub_scores,
        "weights_used": COHERENCE_WEIGHTS,
        "alert_count": alert_count,
        "document_count": document_count,
        "methodology_version": "3.0",  # Updated to 3.0 for v0.3 engine
        "last_updated": last_updated.isoformat(),
    }
