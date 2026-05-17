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
from datetime import UTC, datetime

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
from ..rules_engine.llm_evaluator import LlmRuleEvaluator
from ..rules_engine.registry import list_evaluators
from ..scoring import ScoringService
from .state import (
    ClauseWithEmbedding,
    CoherenceGraphState,
    CrossClausePair,
    NodeOutput,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CATEGORY INFERENCE
# =============================================================================

# Keywords for category inference from clause text/data

def infer_document_type(clause: Clause) -> str:
    """Infer document type from clause data or ID patterns."""
    clause_id = clause.id.lower()
    data_keys = set(clause.data.keys()) if clause.data else set()

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
    enriched: list[ClauseWithEmbedding] = []
    errors: list[str] = []

    # Batch-load pre-computed vectors for RAG similarity, if enabled.
    # Embeddings are produced during document ingestion; this node is
    # read-only and degrades gracefully (empty vector) if the table or
    # session isn't available in the current environment.
    embeddings_by_clause: dict[str, list[float]] = {}
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
        except Exception as e:  # noqa: BLE001 — degrade gracefully
            logger.warning(f"Embedding batch load failed, continuing without RAG: {e}")
            errors.append(f"Embedding batch load failed: {e}")

    # Enrich clause.data with structured fields the deterministic rules need.
    # Cache-first: DB hit = zero LLM cost; miss = one Claude Haiku call per clause.
    # This runs regardless of low_budget_mode — it serves deterministic rules, not LLM evaluators.
    try:
        from src.coherence.extraction.clause_extractor import enrich_clauses

        enriched_raw = await enrich_clauses(list(state.clauses))
    except Exception as _exc:  # noqa: BLE001 — never block evaluation
        logger.warning("prepare_context: clause enrichment failed, continuing: %s", _exc)
        enriched_raw = list(state.clauses)

    for clause in enriched_raw:
        category = infer_category(clause)
        doc_type = infer_document_type(clause)

        enriched_clause = ClauseWithEmbedding(
            clause=clause,
            embedding=embeddings_by_clause.get(clause.id, []),
            category=category,
            document_type=doc_type,
        )
        enriched.append(enriched_clause)

    # Identify cross-clause pairs by matching categories
    cross_pairs: list[CrossClausePair] = []

    if state.config.include_cross_clause and len(enriched) > 1:
        # Group by category
        by_category: dict[str, list[ClauseWithEmbedding]] = {}
        for ec in enriched:
            by_category.setdefault(ec.category, []).append(ec)

        # Create pairs within categories that need cross-checking
        # Focus on BUDGET-TIME, BUDGET-SCOPE, TIME-TECHNICAL relationships
        cross_check_pairs = [
            ("BUDGET", "TIME"),
            ("BUDGET", "SCOPE"),
            ("TIME", "TECHNICAL"),
            ("SCOPE", "BUDGET"),
        ]

        for cat_a, cat_b in cross_check_pairs:
            clauses_a = by_category.get(cat_a, [])
            clauses_b = by_category.get(cat_b, [])

            for ca in clauses_a[:5]:  # Limit to prevent explosion
                for cb in clauses_b[:5]:
                    if ca.clause_id != cb.clause_id:
                        cross_pairs.append(
                            CrossClausePair(
                                clause_a=ca,
                                clause_b=cb,
                                similarity_score=0.0,
                                match_reason=f"{cat_a}-{cat_b} category cross-check",
                            )
                        )

                        if len(cross_pairs) >= state.config.max_cross_pairs:
                            break
                if len(cross_pairs) >= state.config.max_cross_pairs:
                    break
            if len(cross_pairs) >= state.config.max_cross_pairs:
                break

    logger.info(
        f"prepare_context: {len(enriched)} clauses enriched, "
        f"{len(cross_pairs)} cross-pairs identified"
    )

    return {
        "enriched_clauses": enriched,
        "cross_pairs": cross_pairs,
        "errors": errors,
    }


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
    coverage: dict[str, bool] = {}
    clauses_to_eval = state.clauses

    for clause in clauses_to_eval:
        for evaluator in evaluators:
            category = evaluator.category
            try:
                app_state = evaluator.applicability(clause)
            except Exception as e:  # noqa: BLE001 — applicability must never crash eval
                logger.warning(f"applicability {evaluator.rule_id} failed: {e}")
                app_state = ApplicabilityState.SKIPPED_MISSING_INPUTS

            if app_state == ApplicabilityState.EVALUATED:
                coverage[category] = True
                try:
                    signal = evaluator.evaluate_v3(clause)
                    if signal is not None:
                        signals.append(signal)
                except Exception as e:
                    error_msg = (
                        f"Evaluator {evaluator.rule_id} failed on clause {clause.id}: {e}"
                    )
                    logger.warning(error_msg)
                    errors.append(error_msg)
            else:
                coverage.setdefault(category, False)

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


async def llm_semantic_evaluate_async(state: CoherenceGraphState) -> NodeOutput:
    """
    Run LLM-based semantic analysis on clauses (async version).

    This is Agent B in the coherence architecture - uses LLM to detect
    semantic issues that deterministic rules cannot catch.

    In low_budget_mode, this node is skipped to reduce costs.

    Args:
        state: Current graph state with enriched clauses

    Returns:
        Partial state update with llm_signals, llm_cost_usd, llm_calls_count
    """
    # Skip in low_budget_mode
    if state.config.low_budget_mode:
        logger.info("llm_semantic_evaluate: skipped (low_budget_mode=True)")
        return {
            "llm_signals": [],
            "llm_cost_usd": 0.0,
            "llm_calls_count": 0,
        }

    signals: list[FindingSignal] = []
    errors: list[str] = []
    total_cost = 0.0
    total_calls = 0

    try:
        evaluators: list[LlmRuleEvaluator] = [
            evaluator for evaluator in list_evaluators(
                low_budget_mode=state.config.low_budget_mode,
            )
            if isinstance(evaluator, LlmRuleEvaluator)
        ]

        for clause in state.clauses:
            for evaluator in evaluators:
                try:
                    signal = await evaluator.evaluate_v3_async(clause)
                    if signal is not None:
                        signals.append(signal)
                except Exception as e:
                    error_msg = (
                        f"LLM evaluator {evaluator.rule_id} failed for clause {clause.id}: {e}"
                    )
                    logger.warning(error_msg)
                    errors.append(error_msg)

        # Get cost metrics
        total_cost = sum(getattr(evaluator, "total_cost_usd", 0.0) for evaluator in evaluators)
        total_calls = sum(getattr(evaluator, "llm_calls_count", 0) for evaluator in evaluators)

    except ImportError as e:
        logger.warning(f"LLM evaluator not available: {e}")
        errors.append(f"LLM evaluator import failed: {e}")

    logger.info(
        f"llm_semantic_evaluate: {len(signals)} findings, "
        f"cost=${total_cost:.4f}, calls={total_calls}"
    )

    return {
        "llm_signals": signals,
        "llm_cost_usd": total_cost,
        "llm_calls_count": total_calls,
        "errors": errors,
    }


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

    rag_pairs: list[CrossClausePair] = []
    errors: list[str] = []

    try:
        from uuid import UUID

        from src.core.database import _session_factory

        from ...adapters.persistence.pgvector_embedding_repository import (
            PgvectorEmbeddingRepository,
        )

        project_uuid = UUID(state.project_id) if state.project_id else None
        if not project_uuid:
            logger.warning("rag_similarity_check: No project_id, skipping")
            return {"cross_pairs": []}

        if _session_factory is None:
            logger.warning("rag_similarity_check: _session_factory not initialized")
            return {"cross_pairs": []}

        # Try to resolve tenant_id from state.config
        tenant_uuid = UUID(state.config.tenant_id) if state.config.tenant_id else None

        async with _session_factory() as session:
            repo = PgvectorEmbeddingRepository(session, tenant_id=tenant_uuid)

            embedding_matches = await repo.find_cross_document_pairs(
                project_id=project_uuid,
                similarity_threshold=state.config.similarity_threshold,
                max_pairs=state.config.max_cross_pairs,
            )

            for match in embedding_matches:
                clause_a = next(
                    (c for c in state.enriched_clauses if c.clause_id == str(match.source_clause_id)),
                    None
                )
                clause_b = next(
                    (c for c in state.enriched_clauses if c.clause_id == str(match.target_clause_id)),
                    None
                )

                if clause_a and clause_b:
                    rag_pairs.append(
                        CrossClausePair(
                            clause_a=clause_a,
                            clause_b=clause_b,
                            similarity_score=match.similarity_score,
                            match_reason=match.match_reason,
                        )
                    )

    except ValueError as e:
        error_msg = f"Invalid format: {e}"
        logger.warning(error_msg)
        errors.append(error_msg)
    except ImportError as e:
        logger.warning(f"Embedding repository not available: {e}")
        errors.append(f"RAG similarity check unavailable: {e}")
    except Exception as e:
        logger.error(f"Error in RAG similarity check: {e}")
        errors.append(f"RAG similarity check error: {e}")

    logger.info(f"rag_similarity_check: {len(rag_pairs)} pairs found via embedding similarity")

    return {
        "cross_pairs": rag_pairs,
        "errors": errors,
    }


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
        except Exception as e:
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
    clause_a = pair.clause_a
    clause_b = pair.clause_b

    # Check for budget vs contract total mismatch
    if clause_a.category == "BUDGET" and clause_b.category == "SCOPE":
        budget_total = clause_a.data.get("total") or clause_a.data.get("line_total")
        scope_estimate = clause_b.data.get("estimated_cost") or clause_b.data.get("budget")

        if budget_total and scope_estimate:
            try:
                bt = float(budget_total)
                se = float(scope_estimate)
                if bt > 0 and se > 0:
                    variance = abs(bt - se) / max(bt, se)
                    if variance > 0.1:  # >10% variance
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
            except (ValueError, TypeError):
                pass

    # Check for schedule vs delivery date conflicts
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
            except Exception:
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
        num_rules=27,  # 27 deterministic rules
        poor_extraction_quality=state.config.poor_extraction_quality,
        missing_dimensions=state.config.missing_dimensions or _missing_dimensions(state),
    )

    logger.info(
        f"scoring_arbiter: score={diagnostics.score}, "
        f"findings={diagnostics.total_findings}, "
        f"penalty_density={diagnostics.penalty_density}"
    )

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
    category_breakdown = _build_category_breakdown(state.all_signals, state.score)

    # Build enriched result
    result = EnrichedCoherenceResult(
        overall_score=state.score,
        alerts=alerts,
        category_breakdown=category_breakdown,
        calculated_at=datetime.now(UTC),
        score_version="v1_exponential_decay",
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


def _build_category_breakdown(
    signals: list[FindingSignal],
    overall_score: float | None,
) -> list[CategoryBreakdown]:
    """Build category breakdown from signals."""
    if overall_score is None:
        return []

    expanded_signals: list[tuple[str, FindingSignal]] = []
    for signal in signals:
        affected_categories = signal.raw_data.get("affected_categories") if isinstance(signal.raw_data, dict) else None
        if isinstance(affected_categories, list) and affected_categories:
            for category in affected_categories:
                expanded_signals.append((str(category).upper(), signal))
        else:
            expanded_signals.append((signal.category, signal))

    by_category: dict[str, list[FindingSignal]] = {}
    for category, signal in expanded_signals:
        by_category.setdefault(category, []).append(signal)

    total_deduction = 100.0 - overall_score
    breakdown: list[CategoryBreakdown] = []
    total_impact_sum = sum(signal.impact_score for _, signal in expanded_signals) if expanded_signals else 1

    for category, cat_signals in by_category.items():
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for signal in cat_signals:
            if signal.severity in severity_counts:
                severity_counts[signal.severity] += 1

        cat_impact_sum = sum(signal.impact_score for signal in cat_signals)

        if total_deduction > 0 and total_impact_sum > 0:
            impact_pct = (cat_impact_sum / total_impact_sum) * 100
        else:
            impact_pct = 0.0

        cat_map = {
            "BUDGET": "financial",
            "TIME": "schedule",
            "LEGAL": "legal",
            "SCOPE": "scope",
            "TECHNICAL": "technical",
            "QUALITY": "quality",
            "CROSS": "general",
        }

        breakdown.append(
            CategoryBreakdown(
                category=cat_map.get(category, "general"),
                score=round(max(0.0, 100.0 - (cat_impact_sum * 10)), 2),
                alert_count=len(cat_signals),
                severity_breakdown=SeverityCount(**severity_counts),
                impact_percentage=round(impact_pct, 2),
            )
        )

    breakdown.sort(key=lambda x: x.impact_percentage, reverse=True)

    # Add score=100 entries for canonical categories that had no findings.
    # Absence of alerts means the evaluator found nothing wrong, not that the
    # dimension is unmeasured (unmeasured dimensions appear in score_missing_dimensions).
    scored_categories = {item.category for item in breakdown}
    for canonical, legacy in cat_map.items():
        if legacy not in scored_categories and canonical != "CROSS":
            breakdown.append(
                CategoryBreakdown(
                    category=legacy,
                    score=100.0,
                    alert_count=0,
                    severity_breakdown=SeverityCount(
                        critical=0, high=0, medium=0, low=0, info=0
                    ),
                    impact_percentage=0.0,
                )
            )

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
