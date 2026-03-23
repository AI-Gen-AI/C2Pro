# apps/api/src/coherence/router.py
import os
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.domain.enums import AnalysisStatus
from src.core.middleware.feature_flags import require_feature
from src.core.database import get_session, get_session_with_tenant
from src.core.security import security_scheme
from src.analysis.adapters.persistence.models import Alert, Analysis
from src.coherence.adapters.persistence.models import CoherenceResultORM
from src.documents.adapters.persistence.models import DocumentORM
from src.projects.adapters.persistence.models import ProjectORM
from .engine_v2 import CoherenceEngineV2, EngineConfig
from .models import CoherenceResult, ProjectContext, Clause
from .rules import load_rules

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


def _zeroed_sub_scores() -> dict[str, int]:
    return {category: 0 for category in COHERENCE_CATEGORIES}


def _normalized_sub_scores(raw_scores: dict | None) -> dict[str, int]:
    normalized = _zeroed_sub_scores()
    if not raw_scores:
        return normalized

    for category, score in raw_scores.items():
        category_key = str(category).upper()
        if category_key in normalized and score is not None:
            normalized[category_key] = int(score)
    return normalized


# ---- Dependency for the Coherence Engine ----
def get_coherence_engine():
    """
    Dependency to create and provide a CoherenceEngineV2 instance.
    This loads the rules from the YAML file. In a real application, this
    would be cached or loaded once at startup.
    """
    import structlog
    # Import here to ensure registry is loaded
    from .rules_engine.registry import load_qualitative_rules, LLM_RULE_CONFIGS, DETERMINISTIC_EVALUATORS
    from .rules import Rule

    # Load qualitative (LLM) rules
    load_qualitative_rules()

    logger = structlog.get_logger()
    logger.info(
        "coherence_engine_init",
        deterministic_rules=list(DETERMINISTIC_EVALUATORS.keys()),
        llm_rules=list(LLM_RULE_CONFIGS.keys()),
    )

    # Construct the absolute path to the rules file
    rules_file_path = os.path.join(os.path.dirname(__file__), "initial_rules.yaml")

    if not os.path.exists(rules_file_path):
        raise RuntimeError(f"Coherence rules file not found at {rules_file_path}")

    # Load deterministic rules from YAML
    loaded_rules = load_rules(rules_file_path)
    logger.info("deterministic_rules_loaded", count=len(loaded_rules), rule_ids=[r.id for r in loaded_rules])

    # Add LLM rules to the rules list
    for rule_id, rule_config in LLM_RULE_CONFIGS.items():
        llm_rule = Rule(
            id=rule_id,
            description=rule_config.get("description", ""),
            detection_logic=rule_config.get("detection_logic", ""),
            severity=rule_config.get("severity", "medium"),
            category=rule_config.get("category", "general"),
            evaluator_type="llm",
        )
        loaded_rules.append(llm_rule)
    logger.info("all_rules_loaded", count=len(loaded_rules), rule_ids=[r.id for r in loaded_rules])

    config = EngineConfig(enable_llm_rules=True)
    return CoherenceEngineV2(rules=loaded_rules, config=config)


async def get_clauses_from_rag(
    db: AsyncSession,
    project_id: UUID,
    max_chunks: int = 50,
) -> list[Clause]:
    """Fetch document clauses from RAG chunks."""
    stmt = text("""
        SELECT content, metadata, document_id
        FROM document_chunks
        WHERE project_id = CAST(:project_id AS uuid)
        ORDER BY created_at DESC
        LIMIT :limit
    """)
    result = await db.execute(stmt, {"project_id": str(project_id), "limit": max_chunks})
    rows = result.fetchall()

    clauses = []
    for i, row in enumerate(rows):
        metadata = row[1] or {}
        doc_id = str(row[2]) if row[2] else str(project_id)
        clauses.append(
            Clause(
                id=f"chunk_{i}_{doc_id[:8]}",
                text=row[0],
                data={
                    "document_id": doc_id,
                    "source": "rag_chunk",
                    "category": metadata.get("document_type", "unknown"),
                },
            )
        )
    return clauses


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
    """,
)
async def evaluate_project_coherence(
    payload: CoherenceEvaluateRequest,
    engine: CoherenceEngineV2 = Depends(get_coherence_engine),
    db: AsyncSession = Depends(get_session),
) -> CoherenceResult:
    """
    Evaluates the coherence of a project based on its context.

    - **payload**: Contains project_id (to fetch from RAG) OR explicit clauses
    - **engine**: The coherence engine dependency that performs the evaluation

    Returns the evaluation result, including alerts and a score.
    """
    import structlog
    logger = structlog.get_logger()

    # Determine clauses source
    if payload.clauses:
        clauses = payload.clauses
    elif payload.project_id:
        clauses = await get_clauses_from_rag(db, payload.project_id, payload.max_chunks)
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
        engine_deterministic_rules=len(engine._deterministic_rules),
        engine_llm_rules=len(engine._llm_rules),
    )

    project_context = ProjectContext(
        id=str(payload.project_id) if payload.project_id else "manual",
        clauses=clauses,
    )
    result = await engine.evaluate_async(project_context)

    logger.info(
        "coherence_evaluate_complete",
        alerts_count=len(result.alerts),
        overall_score=result.overall_score,
    )
    return result


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
            select(ProjectORM).where(
                ProjectORM.id == project_id,
                ProjectORM.tenant_id == tenant_id,
            )
        )
        project = project_result.scalar_one_or_none()

        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )

        # Get counts
        document_count = (
            await session.execute(
                select(func.count()).select_from(DocumentORM).where(DocumentORM.project_id == project_id)
            )
        ).scalar_one()
        
        alert_count = (
            await session.execute(
                select(func.count()).select_from(Alert).where(Alert.project_id == project_id)
            )
        ).scalar_one()

        # Fetch latest completed analysis
        latest_analysis = (
            await session.execute(
                select(Analysis)
                .where(
                    Analysis.project_id == project_id,
                    Analysis.status == AnalysisStatus.COMPLETED,
                )
                .order_by(Analysis.completed_at.desc().nullslast(), Analysis.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        # Fetch latest coherence result (legacy or direct engine output)
        coherence_result = (
            await session.execute(
                select(CoherenceResultORM)
                .where(CoherenceResultORM.project_id == project_id)
                .order_by(CoherenceResultORM.calculated_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        # Fetch latest metadata for last_updated
        latest_doc_at = (
            await session.execute(
                select(func.max(DocumentORM.updated_at))
                .where(DocumentORM.project_id == project_id)
            )
        ).scalar_one()
        
        latest_alert_at = (
            await session.execute(
                select(func.max(Alert.updated_at))
                .where(Alert.project_id == project_id)
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
    last_updated = max((c for c in candidates if c is not None), default=datetime.utcnow())

    return {
        "project_id": str(project_id),
        "tenant_id": str(tenant_id),
        "global_score": global_score,
        "coherence_score": global_score,
        "sub_scores": sub_scores,
        "weights_used": COHERENCE_WEIGHTS,
        "alert_count": alert_count,
        "document_count": document_count,
        "methodology_version": "2.1",
        "last_updated": last_updated.isoformat() + "Z" if not last_updated.tzinfo else last_updated.isoformat(),
    }
