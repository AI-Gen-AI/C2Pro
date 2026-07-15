"""
nodes.py — LangGraph Node Implementations for Coherence Engine v0.3

Implements all 7 nodes in the coherence evaluation subgraph:
1. prepare_context - Enrich clauses with categories and prepare for evaluation
2. deterministic_evaluate - Run 27 deterministic rules (Agent A)
3. llm_semantic_evaluate - Run LLM-based semantic analysis (Agent B)
4. cross_clause_eval - Analyze cross-document relationships
5. scoring_arbiter - Calculate final score from all signals (Agent C)
6. format_output - Format results for API response

Graph topology:
    prepare_context → [det, llm] (parallel) → cross_clause → scoring → format

Location: apps/api/src/coherence/graph/nodes.py
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from itertools import islice, product
from typing import Any

from src.coherence.domain.ports.coherence_llm_gate_port import (
    CoherenceLlmGatePort,
    GateDecision,
)
from src.coherence.domain.v2_constants import SCORE_VERSION_V1
from src.core.observability.coherence_tracing import traced_coherence_node

from ..alert_generator import TEMPLATES  # TASK-COH-V1-06
from ..models import (
    Alert,
    CategoryBreakdown,
    Clause,
    EnrichedCoherenceResult,
    Evidence,
    FindingSignal,
    SeverityCount,
    impact_to_severity,
)
from ..rules_engine.base import ApplicabilityState
from ..rules_engine.category_utils import infer_category
from ..rules_engine.registry import list_evaluators
from ..scoring import ScoringService
from .state import (
    ClauseWithEmbedding,
    CoherenceGraphState,
    CrossClausePair,
    EvaluationConfig,
    NodeOutput,
)

logger = logging.getLogger(__name__)

_EXPECTED_EVALUATOR_ERRORS = (
    ArithmeticError,
    AttributeError,
    LookupError,
    RuntimeError,
    TypeError,
    ValueError,
)
_CATEGORY_CROSS_CHECK_PAIRS = (
    ("BUDGET", "TIME"),
    ("BUDGET", "SCOPE"),
    ("TIME", "TECHNICAL"),
    ("SCOPE", "BUDGET"),
)


@dataclass
class _GateAccum:
    signals: list[FindingSignal] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    coverage: dict[str, bool] = field(default_factory=dict)
    total_cost: float = 0.0
    total_calls: int = 0
    skipped_not_applicable: int = 0
    skipped_non_substantive: int = 0
    budget_reset: date | None = None
    budget_exhausted_seen: bool = False

logger.setLevel(logging.INFO)
if not any(
    getattr(handler, "name", None) == "coherence_graph_nodes_stream"
    for handler in logger.handlers
):
    _stream_handler = logging.StreamHandler()
    _stream_handler.set_name("coherence_graph_nodes_stream")
    _stream_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_stream_handler)


# =============================================================================
# CATEGORY INFERENCE
# =============================================================================

# Keywords for category inference from clause text/data

def infer_document_type(clause: Clause) -> str:
    """Infer document type from clause data or ID patterns."""
    clause_id = clause.id.lower()
    data_keys = set(clause.data.keys()) if clause.data else set()
    data_doc_type = clause.data.get("document_type") if clause.data else None

    if data_doc_type:
        return str(data_doc_type).strip().lower()

    # Check data keys for strong indicators
    if {"unit_price", "quantity", "line_total"} & data_keys:
        return "budget"
    if {"start_date", "end_date", "predecessor"} & data_keys:
        return "schedule"
    if {"lead_time", "required_on_site_date"} & data_keys:
        return "bom"

    # Check ID patterns
    if any(x in clause_id for x in ["budget", "bud", "cost"]):
        return "budget"
    if any(x in clause_id for x in ["schedule", "task", "milestone"]):
        return "schedule"
    if any(x in clause_id for x in ["bom", "material", "component"]):
        return "bom"
    if any(x in clause_id for x in ["contract", "clause", "legal"]):
        return "contract"

    return "other"


_ROUTER_DOC_TYPE_ALIASES = {
    "boq": "budget_boq",
    "budget": "budget_boq",
    "gantt": "schedule_gantt",
    "schedule": "schedule_gantt",
    "specification": "technical_spec",
    "technical": "technical_spec",
}

_ROUTER_CATEGORY_TO_COVERAGE = {
    "SCHEDULE": "TIME",
}


def _routing_coverage_priors_from_clauses(clauses: list[Clause]) -> dict[str, bool]:
    """Convert CategoryRouter evidence priors into graph coverage flags."""
    if not clauses:
        return {}

    try:
        from src.coherence.application.services.category_router import (
            CategoryRouter,
            ChunkSignal,
        )

        router = CategoryRouter.from_registry()
        coverage: dict[str, bool] = {}
        for clause in clauses:
            doc_type = infer_document_type(clause)
            routed_doc_type = _ROUTER_DOC_TYPE_ALIASES.get(doc_type, doc_type)
            result = router.route(
                chunks=[ChunkSignal(chunk_id=clause.id, text=clause.text)],
                doc_type=routed_doc_type,
                segments=[],
            )
            for category, status in result.category_status.items():
                if status == "has_evidence":
                    canonical = _ROUTER_CATEGORY_TO_COVERAGE.get(
                        category.value, category.value
                    )
                    coverage[canonical] = True
        return coverage
    except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
        logger.warning("category routing coverage priors failed: %s", exc)
        return {}


# =============================================================================
# NODE 1: PREPARE CONTEXT
# =============================================================================


async def prepare_context_async(state: CoherenceGraphState) -> NodeOutput:
    """
    Prepare clauses for evaluation by enriching with categories and embeddings (async version).

    This node:
    1. Converts raw Clause objects to ClauseWithEmbedding
    2. Infers category for each clause
    3. Optionally loads pre-computed embeddings from repository
    4. Identifies potential cross-clause pairs by category

    Note: Embeddings should be pre-computed during document ingestion to ensure
    zero-LLM cost during evaluation. This node only loads existing embeddings.

    Args:
        state: Current graph state with raw clauses

    Returns:
        Partial state update with enriched_clauses and cross_pairs
    """
    errors: list[str] = []
    embeddings_by_clause, embedding_errors = await _load_context_embeddings(state)
    errors.extend(embedding_errors)
    enriched_raw = await _enrich_context_clauses(state.clauses)
    enriched = _build_enriched_clauses(enriched_raw, embeddings_by_clause)
    cross_pairs = _build_category_cross_pairs(enriched, state.config)

    logger.info(
        f"prepare_context: {len(enriched)} clauses enriched, "
        f"{len(cross_pairs)} cross-pairs identified"
    )

    return {
        "enriched_clauses": enriched,
        "cross_pairs": cross_pairs,
        "errors": errors,
    }


async def _load_context_embeddings(
    state: CoherenceGraphState,
) -> tuple[dict[str, list[float]], list[str]]:
    """Load pre-computed vectors for RAG similarity, degrading to empty vectors."""
    embeddings_by_clause: dict[str, list[float]] = {}
    errors: list[str] = []
    if state.config.include_rag_similarity and state.clauses:
        try:
            from uuid import UUID

            from src.core.database import _session_factory

            from ...adapters.persistence.pgvector_embedding_repository import (
                PgvectorEmbeddingRepository,
            )

            project_uuid = UUID(state.project_id) if state.project_id else None
            tenant_uuid = (
                UUID(state.config.tenant_id) if state.config.tenant_id else None
            )

            if project_uuid and _session_factory is not None:
                async with _session_factory() as session:
                    repo = PgvectorEmbeddingRepository(
                        session=session, tenant_id=tenant_uuid
                    )
                    clause_ids = [c.id for c in state.clauses]
                    embeddings_by_clause = await repo.load_embeddings_batch(
                        clause_ids=clause_ids,
                        project_id=project_uuid,
                    )
                logger.debug(
                    "prepare_context: loaded %s/%s embeddings for project %s",
                    len(embeddings_by_clause),
                    len(state.clauses),
                    project_uuid,
                )
        except (ValueError, ImportError) as e:
            logger.warning(f"Could not initialize embedding repository: {e}")
            errors.append(f"Embedding repository unavailable: {e}")
        except PermissionError as e:
            logger.warning(f"Tenant isolation rejected embedding load: {e}")
            errors.append(f"Embedding load denied: {e}")
        except (AttributeError, RuntimeError, TypeError) as e:
            logger.warning(f"Embedding batch load failed, continuing without RAG: {e}")
            errors.append(f"Embedding batch load failed: {e}")

    return embeddings_by_clause, errors


async def _enrich_context_clauses(clauses: list[Clause]) -> list[Clause]:
    """Enrich clause data for deterministic rules without blocking evaluation."""
    try:
        from src.coherence.extraction.clause_extractor import enrich_clauses

        return await enrich_clauses(list(clauses))
    except (AttributeError, ImportError, RuntimeError, TypeError, ValueError) as _exc:
        logger.warning("prepare_context: clause enrichment failed, continuing: %s", _exc)
        return list(clauses)


def _build_enriched_clauses(
    clauses: list[Clause],
    embeddings_by_clause: dict[str, list[float]],
) -> list[ClauseWithEmbedding]:
    """Attach inferred metadata and optional embeddings to clauses."""
    enriched: list[ClauseWithEmbedding] = []
    for clause in clauses:
        category = infer_category(clause)
        doc_type = infer_document_type(clause)

        enriched_clause = ClauseWithEmbedding(
            clause=clause,
            embedding=embeddings_by_clause.get(clause.id, []),
            category=category,
            document_type=doc_type,
        )
        enriched.append(enriched_clause)

    return enriched


def _build_category_cross_pairs(
    enriched: list[ClauseWithEmbedding],
    config: EvaluationConfig,
) -> list[CrossClausePair]:
    """Identify category-based cross-clause pairs."""
    if not config.include_cross_clause or len(enriched) <= 1:
        return []

    by_category: dict[str, list[ClauseWithEmbedding]] = {}
    for ec in enriched:
        by_category.setdefault(ec.category, []).append(ec)

    return list(islice(_iter_category_cross_pairs(by_category), config.max_cross_pairs))


def _iter_category_cross_pairs(
    by_category: dict[str, list[ClauseWithEmbedding]],
) -> Iterator[CrossClausePair]:
    """Yield category cross-check pairs in deterministic priority order."""
    for cat_a, cat_b in _CATEGORY_CROSS_CHECK_PAIRS:
        clauses_a = by_category.get(cat_a, [])[:5]
        clauses_b = by_category.get(cat_b, [])[:5]
        for ca, cb in product(clauses_a, clauses_b):
            if ca.clause_id != cb.clause_id:
                yield CrossClausePair(
                    clause_a=ca,
                    clause_b=cb,
                    similarity_score=0.0,
                    match_reason=f"{cat_a}-{cat_b} category cross-check",
                )


@traced_coherence_node(node_name="prepare_context")
def prepare_context(state: CoherenceGraphState) -> NodeOutput:
    """
    Synchronous wrapper for prepare_context_async.

    LangGraph can call this directly; it handles the async internally.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create a new loop in a thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, prepare_context_async(state))
                return future.result()
        else:
            return loop.run_until_complete(prepare_context_async(state))
    except RuntimeError:
        return asyncio.run(prepare_context_async(state))


# =============================================================================
# NODE 2: DETERMINISTIC EVALUATE
# =============================================================================


@traced_coherence_node(node_name="deterministic_evaluate")
def deterministic_evaluate(state: CoherenceGraphState) -> NodeOutput:
    """
    Run the 12 deterministic v1 evaluators on each clause.

    This is Agent A in the coherence architecture - fast, zero LLM cost,
    high confidence rules that catch structural issues.

    Args:
        state: Current graph state with enriched clauses

    Returns:
        Partial state update with deterministic_signals, coverage_map
        (per-category assessed/skipped), and errors.
    """
    evaluators = [
        evaluator for evaluator in list_evaluators()
        if getattr(evaluator, "source", "deterministic") == "deterministic"
    ]
    signals: list[FindingSignal] = []
    errors: list[str] = []
    coverage = _routing_coverage_priors_from_clauses(state.clauses)
    clauses_to_eval = state.clauses

    for clause in clauses_to_eval:
        clause_signals, clause_errors = _evaluate_deterministic_clause(
            clause, evaluators, coverage
        )
        signals.extend(clause_signals)
        errors.extend(clause_errors)

    logger.info(
        f"deterministic_evaluate: {len(signals)} findings, "
        f"coverage={coverage}"
    )

    return {
        "deterministic_signals": signals,
        "coverage_map": coverage,
        "errors": errors,
    }


# =============================================================================
# NODE 3: LLM SEMANTIC EVALUATE
# =============================================================================


async def llm_semantic_evaluate_async(
    state: CoherenceGraphState,
    *,
    gate: CoherenceLlmGatePort | None = None,
) -> NodeOutput:
    """P3: always-on LLM semantic layer via CoherenceLlmGate.

    For each (clause x R-*-CLARITY rule), consult the gate. Honor the
    test escape hatch (state.config.low_budget_mode=True) to skip entirely.
    """
    from src.coherence.rules_engine.registry import V1_LLM_RULE_IDS

    _LLM_CATEGORIES = ("SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY")

    if state.config.low_budget_mode:
        logger.info("llm_semantic_evaluate: skipped (low_budget_mode=True escape hatch)")
        return {
            "llm_signals": [],
            "llm_cost_usd": 0.0,
            "llm_calls_count": 0,
            "coverage_map": dict.fromkeys(_LLM_CATEGORIES, False),
        }

    if gate is None:
        # Production path: construct CoherenceLlmGate. Per-request DB session
        # is acquired from the existing database helper. If the helper isn't
        # available in this context (e.g. some test contexts), fall back to
        # gate without db -- the cost path will fail-closed to budget_exhausted
        # at the UUID/cost step, surfacing honestly rather than crashing.
        from src.coherence.adapters.ai.coherence_llm_gate import CoherenceLlmGate
        try:
            from src.core import database as _db_mod  # noqa: PLC0415
            _session_factory = getattr(_db_mod, "_session_factory", None)
        except (AttributeError, ImportError):
            _session_factory = None
        if _session_factory is not None:
            async with _session_factory() as session:
                gate = CoherenceLlmGate(db=session)
                return await _run_gate(state, gate, _LLM_CATEGORIES, V1_LLM_RULE_IDS)
        gate = CoherenceLlmGate(db=None)

    return await _run_gate(state, gate, _LLM_CATEGORIES, V1_LLM_RULE_IDS)


async def _run_gate(
    state: CoherenceGraphState,
    gate: CoherenceLlmGatePort,
    _LLM_CATEGORIES: tuple[str, ...],
    rule_ids: tuple[str, ...],
) -> NodeOutput:
    """Inner loop: dispatch each (clause, rule) to the gate and aggregate."""
    accum = _GateAccum(coverage=dict.fromkeys(_LLM_CATEGORIES, False))
    tenant_id = (state.config.tenant_id or "").strip() or \
        "00000000-0000-0000-0000-000000000000"

    for clause in state.clauses:
        await _run_gate_for_clause(clause, rule_ids, gate, tenant_id, accum)

    # INFO-level summary so applicability gating is observable in default logs
    # (per-pair skips are DEBUG and suppressed at INFO; TASK-COH-LLM-APPLIC-009).
    logger.info(
        "coherence_llm_gate.applicability_summary clauses=%d evaluated=%d "
        "skipped_not_applicable=%d skipped_non_substantive=%d",
        len(state.clauses),
        accum.total_calls,
        accum.skipped_not_applicable,
        accum.skipped_non_substantive,
    )

    out: dict[str, Any] = {
        "llm_signals": accum.signals,
        "llm_cost_usd": accum.total_cost,
        "llm_calls_count": accum.total_calls,
        "llm_skipped_count": accum.skipped_not_applicable,
        "skipped_non_substantive_count": accum.skipped_non_substantive,
        "coverage_map": accum.coverage,
        "errors": accum.errors,
    }
    if accum.budget_exhausted_seen:
        out["alerts"] = [_emit_budget_alert(accum.budget_reset)]
        out["budget_exhausted_reset_date"] = accum.budget_reset
    return out


async def _run_gate_for_clause(
    clause: Clause,
    rule_ids: tuple[str, ...],
    gate: CoherenceLlmGatePort,
    tenant_id: str,
    accum: _GateAccum,
) -> None:
    """Evaluate all applicable LLM rules for one clause."""
    clause_category = infer_category(clause)
    if _is_non_substantive_clause(clause):
        accum.skipped_non_substantive += 1
        _log_skipped_non_substantive(clause, clause_category)
        return

    for rule_id in rule_ids:
        cat = _category_for_rule(rule_id)
        if cat != clause_category:
            accum.skipped_not_applicable += 1
            _log_skipped_not_applicable(clause, rule_id, clause_category, cat)
            continue
        await _evaluate_applicable_gate_rule(clause, rule_id, cat, gate, tenant_id, accum)


def _log_skipped_non_substantive(clause: Clause, clause_category: str) -> None:
    logger.debug(
        "coherence_llm_gate.skipped_non_substantive "
        "clause_id=%s clause_category=%s",
        clause.id,
        clause_category,
    )


def _log_skipped_not_applicable(
    clause: Clause,
    rule_id: str,
    clause_category: str,
    rule_category: str,
) -> None:
    logger.debug(
        "coherence_llm_gate.skipped_not_applicable "
        "clause_id=%s rule_id=%s clause_category=%s rule_category=%s",
        clause.id,
        rule_id,
        clause_category,
        rule_category,
    )


async def _evaluate_applicable_gate_rule(
    clause: Clause,
    rule_id: str,
    category: str,
    gate: CoherenceLlmGatePort,
    tenant_id: str,
    accum: _GateAccum,
) -> None:
    try:
        decision: GateDecision = await gate.evaluate_rule(tenant_id, rule_id, clause)
    except Exception as e:  # noqa: BLE001
        msg = f"LLM gate {rule_id} failed for clause {clause.id}: {e}"
        logger.warning(msg)
        accum.errors.append(msg)
        return

    accum.total_calls += 1
    if decision.state in ("evaluated", "cache_hit"):
        if decision.finding is not None:
            accum.signals.append(decision.finding)
        accum.coverage[category] = True
        accum.total_cost += decision.cost_charged_usd
    elif decision.state == "budget_exhausted":
        accum.budget_exhausted_seen = True
        if accum.budget_reset is None or (
            decision.reset_date and decision.reset_date < accum.budget_reset
        ):
            accum.budget_reset = decision.reset_date


def _evaluate_deterministic_clause(
    clause: Clause,
    evaluators: list[Any],
    coverage: dict[str, bool],
) -> tuple[list[FindingSignal], list[str]]:
    """Run deterministic evaluators for one clause."""
    signals: list[FindingSignal] = []
    errors: list[str] = []
    for evaluator in evaluators:
        category = evaluator.category
        app_state = _deterministic_applicability(evaluator, clause)
        if app_state != ApplicabilityState.EVALUATED:
            coverage.setdefault(category, False)
            continue

        coverage[category] = True
        try:
            signal = evaluator.evaluate_v3(clause)
            if signal is not None:
                signals.append(signal)
        except _EXPECTED_EVALUATOR_ERRORS as e:
            error_msg = f"Evaluator {evaluator.rule_id} failed on clause {clause.id}: {e}"
            logger.warning(error_msg)
            errors.append(error_msg)
    return signals, errors


def _deterministic_applicability(evaluator: Any, clause: Clause) -> ApplicabilityState:
    """Return evaluator applicability while letting unexpected defects propagate."""
    try:
        return evaluator.applicability(clause)
    except _EXPECTED_EVALUATOR_ERRORS as e:
        logger.warning(f"applicability {evaluator.rule_id} failed: {e}")
        return ApplicabilityState.SKIPPED_MISSING_INPUTS


_RULE_TO_CATEGORY: dict[str, str] = {
    "R-SCOPE-CLARITY-01": "SCOPE",
    "R-PAYMENT-CLARITY-01": "BUDGET",
    "R-SCHEDULE-CLARITY-01": "TIME",
    "R-TECHNICAL-SPEC-CLARITY-01": "TECHNICAL",
    "R-RESPONSIBILITY-01": "LEGAL",
    "R-QUALITY-STANDARDS-01": "QUALITY",
}


def _category_for_rule(rule_id: str) -> str:
    """Map LLM rule_id -> canonical category. Mirrors V1_LLM_RULE_IDS registry order.

    Unknown rule_ids log a warning (loudly surfaces config drift between
    V1_LLM_RULE_IDS and this mapping) and fall back to SCOPE.
    """
    cat = _RULE_TO_CATEGORY.get(rule_id)
    if cat is None:
        logger.warning(
            "_category_for_rule.unknown_rule_id rule_id=%r defaulting=SCOPE", rule_id
        )
        return "SCOPE"
    return cat


_OBLIGATION_RE = re.compile(
    r"\b("
    r"shall|must|will|requires?|provide|deliver|perform|maintain|submit|"
    r"debera|deberá|debe|sera|será|realizara|realizará|proporcionara|"
    r"proporcionará|entregara|entregará|mantendra|mantendrá|presentara|"
    r"presentará"
    r")\b",
    re.IGNORECASE,
)

_HEADING_RE = re.compile(
    r"^\s*(?:"
    r"(?:appendix|annex|schedule|price schedule|section|chapter|capitulo|"
    r"capítulo|anexo)\s+[\w.\- ]{0,80}|"
    r"\d+(?:\.\d+){0,4}\s+[^\.;:]{1,100}|"
    r"[ivxlcdm]+\)\s+[^\.;:]{1,100}"
    r")\s*$",
    re.IGNORECASE,
)


def _is_non_substantive_clause(clause: Clause) -> bool:
    """Return True for headings/table rows that should not consume an LLM rule.

    This is deliberately conservative: substantive clauses with obligation verbs
    still reach the category-matched LLM rule, while BOM rows, synthetic budget
    reconciliation clauses, and bare headings/list rows are skipped.
    """
    text = (clause.text or "").strip()
    data = clause.data or {}
    source = str(data.get("source", "")).lower()
    if source == "procurement_bom":
        return True

    lowered = text.lower()
    if lowered == "project budget vs contract reconciliation":
        return True
    if not text:
        return True
    if _looks_like_reference_list(text):
        return True
    if _OBLIGATION_RE.search(text):
        return False

    words = re.findall(r"\b[\wÀ-ÿ]+\b", text)
    if len(words) <= 3:
        return True
    if lowered.endswith(("certificate.", "certificate")) and len(words) <= 6:
        return True
    if text == text.upper() and len(words) <= 12:
        return True
    return bool(_HEADING_RE.match(text) and len(words) <= 12)


def _looks_like_reference_list(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    reference_lines = 0
    for line in lines:
        lower = line.lower()
        words = re.findall(r"\b[\wÀ-ÿ]+\b", line)
        if (
            lower.startswith(("appendix", "annex", "schedule"))
            or "certificate" in lower
            or len(words) <= 6
        ):
            reference_lines += 1
    return reference_lines == len(lines)


def _emit_budget_alert(reset_date: date | None) -> Alert:
    """One advisory per evaluation when >=1 rule denied for budget_exhausted."""
    msg = "Deep semantic analysis paused: tenant analysis budget exhausted."
    if reset_date is not None:
        msg = f"{msg} Resets {reset_date}."
    return Alert(
        rule_id="ADV-BUDGET-EXHAUSTED",
        severity="low",  # template registered AlertSeverity.LOW in Task 8
        category="general",
        message=msg,
        evidence=Evidence(
            claim="tenant_budget_exhausted",
            source_clause_id="",
            quote="",
        ),
    )


def llm_semantic_evaluate(state: CoherenceGraphState) -> NodeOutput:
    """
    Synchronous wrapper for llm_semantic_evaluate_async.

    LangGraph can call this directly; it handles the async internally.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create a new loop in a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    llm_semantic_evaluate_async(state)
                )
                return future.result()
        else:
            return loop.run_until_complete(llm_semantic_evaluate_async(state))
    except RuntimeError:
        return asyncio.run(llm_semantic_evaluate_async(state))


# =============================================================================
# NODE 3.5: RAG SIMILARITY CHECK
# =============================================================================


async def rag_similarity_check_async(state: CoherenceGraphState) -> NodeOutput:
    """
    Use embedding similarity to find cross-document clause pairs (async version).

    This is Agent A+ in the coherence architecture - uses zero-LLM-cost
    vector similarity search to detect semantically related clauses across
    different documents.
    """
    if not state.config.include_rag_similarity:
        logger.info("rag_similarity_check: skipped (include_rag_similarity=False)")
        return {"cross_pairs": []}

    if not state.enriched_clauses:
        logger.info("rag_similarity_check: skipped (no enriched clauses)")
        return {"cross_pairs": []}

    errors: list[str] = []

    try:
        rag_pairs = await _load_rag_similarity_pairs(state)

    except ValueError as e:
        error_msg = f"Invalid format: {e}"
        logger.warning(error_msg)
        errors.append(error_msg)
        rag_pairs = []
    except ImportError as e:
        logger.warning(f"Embedding repository not available: {e}")
        errors.append(f"RAG similarity check unavailable: {e}")
        rag_pairs = []

    logger.info(f"rag_similarity_check: {len(rag_pairs)} pairs found via embedding similarity")

    return {
        "cross_pairs": rag_pairs,
        "errors": errors,
    }


async def _load_rag_similarity_pairs(state: CoherenceGraphState) -> list[CrossClausePair]:
    """Load cross-document RAG similarity pairs from pgvector."""
    from uuid import UUID

    from src.core.database import _session_factory

    from ...adapters.persistence.pgvector_embedding_repository import (
        PgvectorEmbeddingRepository,
    )

    project_uuid = UUID(state.project_id) if state.project_id else None
    if not project_uuid:
        logger.warning("rag_similarity_check: No project_id, skipping")
        return []

    if _session_factory is None:
        logger.warning("rag_similarity_check: _session_factory not initialized")
        return []

    tenant_uuid = UUID(state.config.tenant_id) if state.config.tenant_id else None
    async with _session_factory() as session:
        repo = PgvectorEmbeddingRepository(session, tenant_id=tenant_uuid)
        embedding_matches = await repo.find_cross_document_pairs(
            project_id=project_uuid,
            similarity_threshold=state.config.similarity_threshold,
            max_pairs=state.config.max_cross_pairs,
        )
    return _pairs_from_embedding_matches(state.enriched_clauses, embedding_matches)


def _pairs_from_embedding_matches(
    enriched_clauses: list[ClauseWithEmbedding],
    embedding_matches: list[Any],
) -> list[CrossClausePair]:
    """Convert repository similarity matches into graph cross-clause pairs."""
    by_clause_id = {clause.clause_id: clause for clause in enriched_clauses}
    pairs: list[CrossClausePair] = []
    for match in embedding_matches:
        clause_a = by_clause_id.get(str(match.source_clause_id))
        clause_b = by_clause_id.get(str(match.target_clause_id))
        if clause_a and clause_b:
            pairs.append(
                CrossClausePair(
                    clause_a=clause_a,
                    clause_b=clause_b,
                    similarity_score=match.similarity_score,
                    match_reason=match.match_reason,
                )
            )
    return pairs


@traced_coherence_node(node_name="rag_similarity_check")
def rag_similarity_check(state: CoherenceGraphState) -> NodeOutput:
    """
    Synchronous wrapper for rag_similarity_check_async.

    LangGraph can call this directly; it handles the async internally.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create a new loop in a thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run, rag_similarity_check_async(state)
                )
                return future.result()
        else:
            return loop.run_until_complete(rag_similarity_check_async(state))
    except RuntimeError:
        return asyncio.run(rag_similarity_check_async(state))


# =============================================================================
# NODE 4: CROSS-CLAUSE EVAL
# =============================================================================


@traced_coherence_node(node_name="cross_clause_eval")
def cross_clause_eval(state: CoherenceGraphState) -> NodeOutput:
    """
    Analyze relationships between clause pairs for coherence issues.

    Checks for:
    - Contradictions between clauses
    - Inconsistent terminology
    - Conflicting obligations or timelines
    - Scope gaps

    In low_budget_mode, uses heuristic checks instead of LLM.

    Args:
        state: Current graph state with cross_pairs

    Returns:
        Partial state update with cross_signals
    """
    if not state.config.include_cross_clause or not state.cross_pairs:
        logger.info("cross_clause_eval: skipped (no pairs or disabled)")
        return {"cross_signals": []}

    signals: list[FindingSignal] = []
    errors: list[str] = []

    for pair in state.cross_pairs:
        try:
            # Heuristic cross-clause checks (no LLM)
            signal = _check_cross_clause_heuristic(pair)
            if signal is not None:
                signals.append(signal)
        except (AttributeError, RuntimeError, TypeError, ValueError) as e:
            error_msg = f"Cross-clause check failed: {e}"
            logger.warning(error_msg)
            errors.append(error_msg)

    logger.info(f"cross_clause_eval: {len(signals)} cross-clause findings")

    return {
        "cross_signals": signals,
        "errors": errors,
    }


def _check_cross_clause_heuristic(pair: CrossClausePair) -> FindingSignal | None:
    """
    Perform heuristic cross-clause analysis without LLM.

    Checks for obvious mismatches like:
    - Budget totals not matching across documents
    - Schedule dates conflicting with delivery dates
    - Scope items without budget coverage
    """
    return _check_budget_scope_mismatch(pair) or _check_schedule_delivery_conflict(pair)


def _check_budget_scope_mismatch(pair: CrossClausePair) -> FindingSignal | None:
    """Check for budget vs contract total mismatch."""
    clause_a = pair.clause_a
    clause_b = pair.clause_b
    if clause_a.category != "BUDGET" or clause_b.category != "SCOPE":
        return None

    budget_total = clause_a.data.get("total") or clause_a.data.get("line_total")
    scope_estimate = clause_b.data.get("estimated_cost") or clause_b.data.get("budget")
    if not budget_total or not scope_estimate:
        return None

    try:
        bt = float(budget_total)
        se = float(scope_estimate)
    except (ValueError, TypeError):
        return None

    if bt <= 0 or se <= 0:
        return None

    variance = abs(bt - se) / max(bt, se)
    if variance <= 0.1:
        return None

    impact = min(0.8, 0.3 + variance)
    return FindingSignal(
        rule_id="CROSS-BUDGET-SCOPE",
        clause_id=f"{clause_a.clause_id}|{clause_b.clause_id}",
        source="deterministic",
        impact_score=impact,
        confidence=0.85,
        severity=impact_to_severity(impact),
        category="CROSS",
        evidence_summary=(
            f"Budget ({bt:,.2f}) and scope estimate ({se:,.2f}) "
            f"differ by {variance*100:.1f}%"
        ),
        quote=f"Budget: {clause_a.text[:100]}... | Scope: {clause_b.text[:100]}...",
        raw_data={
            "budget_total": bt,
            "scope_estimate": se,
            "variance_pct": round(variance * 100, 2),
        },
    )


def _check_schedule_delivery_conflict(pair: CrossClausePair) -> FindingSignal | None:
    """Check for schedule vs delivery date conflicts."""
    clause_a = pair.clause_a
    clause_b = pair.clause_b
    if clause_a.category == "TIME" and clause_b.category == "TECHNICAL":
        task_end = clause_a.data.get("end_date")
        required_date = clause_b.data.get("required_on_site_date")

        if task_end and required_date:
            # Simple string comparison for dates (YYYY-MM-DD format)
            try:
                if str(task_end) > str(required_date):
                    return FindingSignal(
                        rule_id="CROSS-SCHEDULE-DELIVERY",
                        clause_id=f"{clause_a.clause_id}|{clause_b.clause_id}",
                        source="deterministic",
                        impact_score=0.7,
                        confidence=0.9,
                        severity="high",
                        category="CROSS",
                        evidence_summary=(
                            f"Task end date ({task_end}) is after "
                            f"required delivery date ({required_date})"
                        ),
                        quote="",
                        raw_data={
                            "task_end_date": str(task_end),
                            "required_on_site_date": str(required_date),
                        },
                    )
            except (TypeError, ValueError):
                pass

    return None


# =============================================================================
# NODE 5: SCORING ARBITER
# =============================================================================


@traced_coherence_node(node_name="scoring_arbiter")
def scoring_arbiter(state: CoherenceGraphState) -> NodeOutput:
    """
    Calculate final coherence score from all finding signals.

    This is Agent C in the coherence architecture - combines signals
    from deterministic rules, LLM analysis, and cross-clause checks
    into a single coherence score.

    Uses exponential decay formula:
        score = 100 × e^(-λ × penalty_density)

    Args:
        state: Current graph state with all signals

    Returns:
        Partial state update with all_signals, score, diagnostics
    """
    # Combine all signals
    all_signals = (
        list(state.deterministic_signals)
        + list(state.llm_signals)
        + list(state.cross_signals)
    )

    # Calculate score
    scoring_service = ScoringService()
    diagnostics = scoring_service.calculate_detailed(
        signals=all_signals,
        num_clauses=len(state.clauses),
        num_rules=12,
        poor_extraction_quality=state.config.poor_extraction_quality,
        coverage_map=state.coverage_map,
    )

    logger.info(
        f"scoring_arbiter: score={diagnostics.score}, "
        f"findings={diagnostics.total_findings}, "
        f"penalty_density={diagnostics.penalty_density}"
    )

    # P3 Task 11: surface budget-throttled categories so the breakdown can
    # report state="budget_throttled" instead of generic "unassessed" when
    # the LLM gate denied the only rule for a category due to tenant cap.
    # The LLM node emits an ADV-BUDGET-EXHAUSTED alert into state.alerts
    # whenever any rule was budget-denied; treat every unassessed canonical
    # category as throttled in that case.
    budget_throttled: list[str] = []
    budget_exhausted = any(
        getattr(a, "rule_id", None) == "ADV-BUDGET-EXHAUSTED"
        for a in (state.alerts or [])
    )
    if budget_exhausted:
        for cat in ("SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"):
            if not state.coverage_map.get(cat, False):
                budget_throttled.append(cat)

    return {
        "all_signals": all_signals,
        "score": diagnostics.score,
        "diagnostics": {
            "total_findings": diagnostics.total_findings,
            "deterministic_findings": diagnostics.deterministic_findings,
            "llm_findings": diagnostics.llm_findings,
            "severity_distribution": diagnostics.severity_distribution,
            "avg_impact": diagnostics.avg_impact,
            "avg_confidence": diagnostics.avg_confidence,
            "scope_factor": diagnostics.scope_factor,
            "penalty_density": diagnostics.penalty_density,
            "raw_penalty_sum": diagnostics.raw_penalty_sum,
            "category_contributions": diagnostics.category_contributions,
            "reason": diagnostics.reason,
            "missing_dimensions": diagnostics.missing_dimensions,
            "category_scores": diagnostics.category_scores,
            "audit_coverage": diagnostics.audit_coverage,
            "budget_throttled_categories": budget_throttled,
        },
    }


# =============================================================================
# NODE 6: FORMAT OUTPUT
# =============================================================================


@traced_coherence_node(node_name="format_output")
def format_output(state: CoherenceGraphState) -> NodeOutput:
    """
    Format the evaluation results into the final API response structure.

    Converts FindingSignals to legacy Alert objects for backward compatibility
    and builds the EnrichedCoherenceResult.

    Args:
        state: Current graph state with score and signals

    Returns:
        Partial state update with alerts and result
    """
    # Convert signals to alerts for backward compat
    alerts = [_signal_to_alert(s) for s in state.all_signals]

    # TASK-COH-V1-06: Handle insufficient_evidence -> AUDIT_INCOMPLETE alert
    if state.score is None:
        missing_dims = state.diagnostics.get("missing_dimensions", [])
        if missing_dims:
            meta_alert = _create_audit_incomplete_alert(
                project_id=state.project_id,
                missing_dimensions=missing_dims,
            )
            alerts.append(meta_alert)

    # Build category breakdown
    category_breakdown = _build_category_breakdown(
        state.all_signals,
        state.coverage_map,
        state.diagnostics.get("category_scores") or {},
        budget_throttled_categories=set(
            state.diagnostics.get("budget_throttled_categories") or []
        ),
    )

    # Build enriched result
    result = EnrichedCoherenceResult(
        overall_score=state.score,
        alerts=alerts,
        category_breakdown=category_breakdown,
        calculated_at=datetime.now(UTC),
        score_version=SCORE_VERSION_V1,
        score_reason=state.diagnostics.get("reason"),
        score_missing_dimensions=state.diagnostics.get("missing_dimensions"),
        finding_signals=state.all_signals,
        deterministic_findings_count=len(state.deterministic_signals),
        llm_findings_count=len(state.llm_signals),
        scope_factor=state.diagnostics.get("scope_factor", 1.0),
        penalty_density=state.diagnostics.get("penalty_density", 0.0),
        avg_impact=state.diagnostics.get("avg_impact", 0.0),
        avg_confidence=state.diagnostics.get("avg_confidence", 0.0),
        llm_cost_usd=state.llm_cost_usd,
        evaluation_mode="low_budget" if state.config.low_budget_mode else "standard",
    )

    logger.info(
        f"format_output: {len(alerts)} alerts, score={state.score}"
    )

    return {
        "alerts": alerts,
        "result": result,
    }


def _signal_to_alert(signal: FindingSignal) -> Alert:
    """Convert a FindingSignal to a legacy Alert object."""
    # Map coherence category to alert category
    category_map = {
        "BUDGET": "financial",
        "TIME": "schedule",
        "LEGAL": "legal",
        "SCOPE": "scope",
        "TECHNICAL": "technical",
        "QUALITY": "quality",
        "CROSS": "general",
    }
    alert_category = category_map.get(signal.category, "general")

    return Alert(
        rule_id=signal.rule_id,
        severity=signal.severity,
        category=alert_category,
        message=signal.evidence_summary,
        evidence=Evidence(
            source_clause_id=signal.clause_id,
            claim=signal.evidence_summary,
            quote=signal.quote or "",
        ),
    )


def _create_audit_incomplete_alert(
    project_id: str,  # noqa: ARG001
    missing_dimensions: list[str],
) -> Alert:
    """Create AUDIT_INCOMPLETE meta-alert when score is None."""
    missing_str = ", ".join(missing_dimensions)
    return Alert(
        rule_id="AUDIT_INCOMPLETE",
        severity="medium",
        category="general",
        message=TEMPLATES["AUDIT_INCOMPLETE"].format(missing_dimensions=missing_str),
        evidence=Evidence(
            source_clause_id="__AUDIT_INCOMPLETE__",
            claim=f"Missing dimensions: {missing_str}",
            quote=(
                "No defensible Coherence Score can be issued without a full triplet "
                "(contract + schedule + budget)."
            ),
        ),
    )


_CAT_LEGACY = {
    "SCOPE": "scope", "BUDGET": "financial", "TIME": "schedule",
    "TECHNICAL": "technical", "LEGAL": "legal", "QUALITY": "quality",
}


def _build_category_breakdown(
    signals: list[FindingSignal],
    coverage_map: dict[str, bool],
    category_scores: dict[str, float | None],
    budget_throttled_categories: set[str] | None = None,
) -> list[CategoryBreakdown]:
    """Honest per-category breakdown: unassessed / assessed_clean / assessed_findings.

    When ``budget_throttled_categories`` is provided, any canonical category
    that would otherwise be reported as ``unassessed`` AND is present in that
    set is upgraded to ``budget_throttled`` instead — surfacing the distinction
    between "no document / no evidence" and "your analysis budget cap was hit".
    """
    breakdown: list[CategoryBreakdown] = []
    # CROSS-category signals are not bucketed into the 6 canonical categories
    # but still count toward total_impact (the impact_percentage denominator).
    total_impact = sum(s.impact_score for s in signals) or 1.0
    for canonical, legacy in _CAT_LEGACY.items():
        cat_signals = [s for s in signals if s.category == canonical]
        sev = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for s in cat_signals:
            if s.severity in sev:
                sev[s.severity] += 1
        assessed = coverage_map.get(canonical, False)
        score = category_scores.get(canonical)
        if not assessed:
            state, baseline_estimated, score = "unassessed", False, None
        elif not cat_signals:
            state, baseline_estimated = "assessed_clean", True
        else:
            state, baseline_estimated = "assessed_findings", False
        # P3: an unassessed category whose LLM-only rule was budget-denied
        # is reported distinctly as "budget_throttled" rather than generic
        # "unassessed", so the dashboard can show "you've hit your analysis
        # cap" vs "upload more documents".
        if (
            not assessed
            and budget_throttled_categories
            and canonical in budget_throttled_categories
        ):
            state, baseline_estimated, score = "budget_throttled", False, None
        cat_impact = sum(s.impact_score for s in cat_signals)
        breakdown.append(
            CategoryBreakdown(
                category=legacy,
                score=score,
                alert_count=len(cat_signals),
                severity_breakdown=SeverityCount(**sev),
                impact_percentage=round(cat_impact / total_impact * 100, 2),
                state=state,
                baseline_estimated=baseline_estimated,
            )
        )
    breakdown.sort(key=lambda b: b.impact_percentage, reverse=True)
    return breakdown


def _missing_dimensions(state: CoherenceGraphState) -> list[str]:
    """Infer missing audit dimensions from prepared clauses."""
    present = {infer_document_type(clause) for clause in state.clauses}
    missing: list[str] = []
    if "schedule" not in present:
        missing.append("schedule")
    if "budget" not in present:
        missing.append("budget")
    return missing


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "prepare_context",
    "prepare_context_async",
    "deterministic_evaluate",
    "llm_semantic_evaluate",
    "llm_semantic_evaluate_async",
    "rag_similarity_check",
    "rag_similarity_check_async",
    "cross_clause_eval",
    "scoring_arbiter",
    "format_output",
    "infer_category",
    "infer_document_type",
]
