"""
Extended LangGraph nodes (N1, N2, N6–N11, N15, N16).

Thin adapter wrappers — business logic lives in domain services and
application use cases. Dependencies resolved lazily to avoid import-time
coupling between bounded contexts.

Refers to TASK-IMPL-010.8–.14 (node refactoring).
"""

from __future__ import annotations

import hashlib
import inspect
import traceback
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import structlog
from langchain_core.messages import AIMessage

from src.analysis.adapters.graph.dependencies import (
    get_ai_service,
    get_anonymization_service,
    get_pii_detector_service,
)
from src.analysis.adapters.graph.risk_signal_bridge import build_risk_signals
from src.analysis.adapters.graph.schema import ProjectState
from src.analysis.application.generate_raci_use_case import (
    GenerateRaciCommand,
    GenerateRaciUseCase,
)
from src.analysis.application.parse_budget_use_case import (
    ParseBudgetCommand,
    ParseBudgetUseCase,
)
from src.analysis.domain.contracts import BudgetItem, Citation
from src.analysis.domain.document_classification import DocumentCategoryClassifier
from src.analysis.domain.documentation_health import build_documentation_health_signal
from src.analysis.domain.node_result import ErrorRecord, NodeResult, NodeStatus

logger = structlog.get_logger()

if TYPE_CHECKING:
    from src.coherence.models import Clause

# ── Domain service instances (stateless, reusable) ──────────────────────────

_document_classifier = DocumentCategoryClassifier()


def _budget_contract_item(item: BudgetItem | dict[str, Any]) -> BudgetItem:
    if isinstance(item, BudgetItem):
        return item
    unknown = set(item) - set(BudgetItem.model_fields)
    if unknown:
        raise ValueError(f"budget_parser emitted unknown contract fields: {sorted(unknown)}")
    return BudgetItem.model_validate(item)


def _budget_contract_payload(item: BudgetItem | dict[str, Any]) -> dict[str, Any]:
    return _budget_contract_item(item).model_dump(mode="python")


def _node_update_with_health(
    update: dict[str, Any],
    *,
    existing_results: list[NodeResult] | None,
) -> dict[str, Any]:
    node_results = [*list(existing_results or []), *list(update.get("node_results") or [])]
    update["documentation_health_signal"] = build_documentation_health_signal(node_results)
    return update


async def _maybe_await(value: object) -> None:
    if inspect.isawaitable(value):
        await value


def _failed_node_result(node: str, exc: Exception) -> NodeResult:
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return NodeResult(
        node=node,
        status=NodeStatus.FAILED,
        error=ErrorRecord(
            node=node,
            error_type=type(exc).__name__,
            message=str(exc),
            traceback_digest=hashlib.sha256(tb.encode("utf-8")).hexdigest()[:16],
        ),
    )


def _ok_node_result(node: str, data: object, confidence: float | None = None) -> NodeResult:
    return NodeResult(node=node, status=NodeStatus.OK, data=data, confidence=confidence)


async def _persist_node_error(state: ProjectState, result: NodeResult) -> None:
    """TS-ADR-013-GRAPH-001 - Persist failed material-node errors to evidence events."""
    if result.error is None:
        return

    tenant_id = state.get("tenant_id")
    project_id = state.get("project_id")
    document_id = state.get("document_id")
    if not tenant_id or not project_id or not document_id:
        logger.warning(
            "node_error_not_persisted_missing_identity",
            node=result.node,
            tenant_id=tenant_id,
            project_id=project_id,
            document_id=document_id,
        )
        return

    try:
        from src.core.database import get_session_with_tenant
        from src.evidence.adapters.persistence.models import EvidenceExtractionEventORM

        async with get_session_with_tenant(UUID(str(tenant_id))) as session:
            session.add(
                EvidenceExtractionEventORM(
                    extraction_run_id=uuid4(),
                    tenant_id=UUID(str(tenant_id)),
                    project_id=UUID(str(project_id)),
                    document_id=UUID(str(document_id)),
                    event_type="processing_error",
                    dimension=None,
                    claim_type="analysis_graph_node",
                    reason="node_failed",
                    payload_trace={
                        "node_result": result.model_dump(mode="json"),
                    },
                )
            )
            await session.flush()
    except Exception as exc:  # noqa: BLE001 - error-event persistence is best-effort.
        logger.warning(
            "node_error_persist_failed",
            node=result.node,
            error=str(exc),
            exc_info=True,
        )


async def _is_feature_v3_coherence_llm_enabled(state: ProjectState) -> bool:
    """TS-ADR-013-GRAPH-001 - Resolve the N8 LLM-on gate from core feature flags."""
    tenant_id = state.get("tenant_id")
    try:
        from src.config import settings

        if tenant_id:
            from src.alerts.adapters.persistence.tenant_repository import (
                SqlAlchemyTenantRepository,
            )
            from src.core.database import get_raw_session
            from src.core.feature_flags import TenantFlagsService

            async with get_raw_session() as session:
                return await TenantFlagsService(
                    tenant_repository=SqlAlchemyTenantRepository(session),
                    settings=settings,
                ).is_enabled(UUID(str(tenant_id)), "feature_v3_coherence_llm")

        return bool(getattr(settings, "feature_v3_coherence_llm", False))
    except Exception as exc:  # noqa: BLE001 - feature flag resolution must fail closed.
        logger.warning(
            "feature_v3_coherence_llm_resolution_failed",
            tenant_id=tenant_id,
            error=str(exc),
        )
        return False


# ---------------------------------------------------------------------------
# N1 — Document Ingestion & Classification
# ---------------------------------------------------------------------------


async def document_ingestion_node(state: ProjectState) -> ProjectState:
    """N1 — Parse the document and classify its coherence category."""
    text = state.get("anonymized_text") or state["document_text"]
    category = _document_classifier.classify(text)

    state["document_parsed"] = True
    state["document_category"] = category
    state["messages"].append(
        AIMessage(content=f"N1 document_ingestion: category={category}")
    )
    logger.info(
        "node_document_ingestion",
        project_id=state.get("project_id"),
        category=category,
    )
    return state


# ---------------------------------------------------------------------------
# N2 — PII Anonymizer
# ---------------------------------------------------------------------------

async def pii_anonymizer_node(state: ProjectState) -> ProjectState:
    """N2 — Detect and redact PII before downstream AI processing."""
    from src.anonymizer.application.anonymization_service import (
        AnonymizationConfig,
        AnonymizationStrategy,
        PiiType,
    )

    text = state["document_text"]
    detector = get_pii_detector_service()
    service = get_anonymization_service(detector)

    config = AnonymizationConfig(
        strategies={pii_type: AnonymizationStrategy.REDACT for pii_type in PiiType}
    )
    anonymized = await service.anonymize(text, config)

    detection_result = await detector.detect(text)
    redactions = [
        {"text": item.text, "type": item.pii_type.name, "start": item.start, "end": item.end}
        for item in detection_result.items
    ]

    state["anonymized_text"] = anonymized
    state["pii_redactions"] = redactions
    state["messages"].append(
        AIMessage(content=f"N2 pii_anonymizer: {len(redactions)} PII items redacted")
    )
    logger.info("node_pii_anonymizer", project_id=state.get("project_id"), pii_count=len(redactions))
    return state


# ---------------------------------------------------------------------------
# N6 — Stakeholder Extractor
# ---------------------------------------------------------------------------

async def stakeholder_extractor_node(state: ProjectState) -> dict[str, Any]:
    """TS-UA-ANA-GRAPH-001 - N6 extracts stakeholders with branch-local graph updates."""
    tenant_id = state.get("tenant_id")
    text = state.get("anonymized_text") or state["document_text"]

    if not tenant_id:
        node_result = NodeResult(
            node="stakeholder_extractor",
            status=NodeStatus.SKIPPED,
            degradation_reason="missing_tenant_id",
        )
        return {
            "extracted_stakeholders": [],
            "node_results": [node_result],
            "messages": [AIMessage(content="N6 stakeholder_extractor: skipped (missing tenant)")],
        }

    try:
        from src.core.ai.anthropic_wrapper import get_anthropic_wrapper
        from src.stakeholders.application.extract_stakeholders import (
            ExtractStakeholdersUseCase as AIExtractStakeholders,
        )

        use_case = AIExtractStakeholders(ai_provider=get_anthropic_wrapper())
        stakeholders = await use_case.execute(contract_text=text, tenant_id=UUID(tenant_id))
        result = [
            {
                "name": getattr(s, "name", None),
                "role": getattr(s, "role", None),
                "company_name": getattr(s, "company_name", None),
                "is_legal_entity": getattr(s, "is_legal_entity", False),
            }
            for s in stakeholders
        ]
    except Exception as exc:
        logger.warning("node_stakeholder_extractor_failed", exc_info=True)
        node_result = _failed_node_result("stakeholder_extractor", exc)
        await _maybe_await(_persist_node_error(state, node_result))
        result = []
        return {
            "extracted_stakeholders": result,
            "node_results": [node_result],
            "messages": [
                AIMessage(content="N6 stakeholder_extractor: failed (see node_results)")
            ],
        }

    return {
        "extracted_stakeholders": result,
        "node_results": [_ok_node_result("stakeholder_extractor", result)],
        "messages": [AIMessage(content=f"N6 stakeholder_extractor: {len(result)} stakeholders found")],
    }


# ---------------------------------------------------------------------------
# N7 — RACI Generator
# ---------------------------------------------------------------------------

async def raci_generator_node(state: ProjectState) -> dict[str, Any]:
    """TS-UA-ANA-GRAPH-001 - N7 generates RACI output with branch-local graph updates."""
    stakeholders = state.get("extracted_stakeholders", [])
    wbs_items = state.get("extracted_wbs", [])

    if not stakeholders or not wbs_items:
        return {
            "raci_matrix": [],
            "messages": [
                AIMessage(
                    content=(
                        f"N7 raci_generator: skipped "
                        f"(stakeholders={len(stakeholders)}, wbs={len(wbs_items)})"
                    )
                )
            ],
        }

    use_case = GenerateRaciUseCase(ai=get_ai_service(state.get("tenant_id")))
    matrix = await use_case.execute(
        GenerateRaciCommand(stakeholders=stakeholders, wbs_items=wbs_items)
    )

    return {
        "raci_matrix": matrix,
        "messages": [AIMessage(content=f"N7 raci_generator: {len(matrix)} assignments generated")],
    }


# ---------------------------------------------------------------------------
# N8 — Coherence Scorer (delegates to canonical 7-node subgraph)
# ---------------------------------------------------------------------------

async def coherence_scorer_node(state: ProjectState) -> dict[str, Any]:
    """TS-UA-ANA-GRAPH-001 - N8 calculates coherence with branch-local graph updates.

    Refers to Suite ID: TS-UA-ANA-UC-001.
    """
    project_id = state.get("project_id")

    if not project_id:
        node_result = NodeResult(
            node="coherence_scorer",
            status=NodeStatus.SKIPPED,
            degradation_reason="missing_project_id",
        )
        return {
            "coherence_score": None,
            "coherence_breakdown": {},
            "coherence_reason": "missing_project_id",
            "coherence_missing_dimensions": ["schedule", "budget"],
            "node_results": [node_result],
            "messages": [AIMessage(content="N8 coherence_scorer: skipped (missing project_id)")],
        }

    try:
        from src.analysis.domain.coherence_derivation import (
            CoherenceDerivationInput,
            CoherenceScoringDerivationService,
        )
        from src.coherence.graph.graph import evaluate_coherence_async
        from src.coherence.graph.state import EvaluationConfig

        derivation = CoherenceScoringDerivationService().derive(
            CoherenceDerivationInput(
                extracted_risks=state.get("extracted_risks", []),
                extracted_wbs=state.get("extracted_wbs", []),
                bom_items=state.get("bom_items", []),
                confidence_score=state.get("confidence_score", 0.0),
                document_text=state.get("document_text", ""),
            )
        )

        clauses = _build_coherence_clauses(state)
        missing_dimensions = _missing_audit_dimensions(state)

        # Interim bridge: convert LLM-extracted risks into FindingSignals
        # so LEGAL/TECHNICAL/QUALITY categories appear as assessed_findings
        # instead of unassessed. Removed when ADR-011 2A.5 wires the
        # evidence module through the pipeline.
        extracted_risks = state.get("extracted_risks", [])
        clause_id = clauses[0].id if clauses else "contract-document"
        bridge_result = build_risk_signals(extracted_risks, clause_id=clause_id)
        logger.info(
            "node_coherence_scorer_bridge",
            extra={
                "risks_in": len(extracted_risks),
                "signals_out": len(bridge_result.signals),
                "coverage_seed": list(bridge_result.coverage_seed.keys()),
                "dropped": bridge_result.dropped_reasons,
            },
        )

        feature_v3_coherence_llm = await _is_feature_v3_coherence_llm_enabled(state)
        result = await evaluate_coherence_async(
            clauses=clauses,
            project_id=project_id,
            config=EvaluationConfig(
                low_budget_mode=not feature_v3_coherence_llm,
                tenant_id=state.get("tenant_id"),
                project_id=project_id,
                poor_extraction_quality=derivation.poor_extraction_quality,
                missing_dimensions=missing_dimensions,
            ),
            seed_signals=list(bridge_result.signals),
            seed_coverage=bridge_result.coverage_seed,
        )
        score = result.overall_score
        breakdown: dict[str, Any] = {
            item.category: item.score
            for item in result.category_breakdown
        }
        quality_note = derivation.quality_note
        reason = result.score_reason
        result_missing_dimensions = result.score_missing_dimensions or missing_dimensions
        bridge_marker = (
            f" bridge[seeded={len(bridge_result.signals)},"
            f"cov={','.join(sorted(bridge_result.coverage_seed)) or '∅'}]"
        )
        node_result = _ok_node_result(
            "coherence_scorer",
            {
                "score": score,
                "breakdown": breakdown,
                "reason": reason,
                "missing_dimensions": result_missing_dimensions,
            },
        )
    except Exception as exc:
        logger.warning("node_coherence_scorer_failed", exc_info=True)
        node_result = _failed_node_result("coherence_scorer", exc)
        await _maybe_await(_persist_node_error(state, node_result))
        score = None
        breakdown = {}
        quality_note = ""
        reason = "node_failed"
        result_missing_dimensions = ["schedule", "budget"]
        bridge_marker = " bridge[error]"

    risk_count = len(state.get("extracted_risks", []))
    wbs_count = len(state.get("extracted_wbs", []))

    return {
        "coherence_score": score,
        "coherence_breakdown": breakdown,
        "coherence_reason": reason,
        "coherence_missing_dimensions": result_missing_dimensions,
        "node_results": [node_result],
        "messages": [
            AIMessage(
                content=f"N8 coherence_scorer: score={score} "
                f"(derived from {risk_count} risks, {wbs_count} WBS items"
                f"{quality_note}){bridge_marker}"
            )
        ],
    }


def _build_coherence_clauses(state: ProjectState) -> list[Clause]:
    """Build canonical subgraph clauses from the analysis graph state."""
    from src.coherence.models import Clause

    document_id = state.get("document_id") or "document"
    doc_type = state.get("doc_type") or state.get("document_category") or "contract"
    return [
        Clause(
            id=f"{doc_type}-{document_id}",
            text=state.get("anonymized_text") or state.get("document_text", ""),
            data={
                "document_type": doc_type,
                "risks": state.get("extracted_risks", []),
                "wbs": state.get("extracted_wbs", []),
                "bom_items": state.get("bom_items", []),
            },
        )
    ]


def _missing_audit_dimensions(state: ProjectState) -> list[str]:
    """Infer missing schedule/budget dimensions for contract-only uploads."""
    doc_type = (state.get("doc_type") or state.get("document_category") or "").lower()
    missing: list[str] = []
    if doc_type != "schedule" and not state.get("extracted_wbs"):
        missing.append("schedule")
    if doc_type != "budget" and not state.get("bom_items"):
        missing.append("budget")
    return missing


# ---------------------------------------------------------------------------
# N9 — Budget Parser (extended with BOM builder)
# ---------------------------------------------------------------------------

async def budget_parser_extended_node(state: ProjectState) -> ProjectState:
    """N9 — Delegates budget parsing + BOM extraction to ParseBudgetUseCase."""
    text = state.get("anonymized_text") or state["document_text"]
    tenant_id = state.get("tenant_id")

    try:
        use_case = ParseBudgetUseCase(ai=get_ai_service(tenant_id))
        result = await use_case.execute(ParseBudgetCommand(text=text))
        bom_items = [_budget_contract_payload(item) for item in result.bom_items]
    except Exception as exc:
        logger.warning("node_budget_parser_failed", exc_info=True)
        node_result = _failed_node_result("budget_parser", exc)
        await _maybe_await(_persist_node_error(state, node_result))
        state["bom_items"] = []
        state["extracted_wbs"] = state.get("extracted_wbs") or []
        state["confidence_score"] = 0.0
        state["node_results"] = [*state.get("node_results", []), node_result]
        state["messages"].append(
            AIMessage(content="N9 budget_parser: failed (see node_results)")
        )
        return state

    state["bom_items"] = bom_items
    state["extracted_wbs"] = state.get("extracted_wbs") or []
    state["confidence_score"] = result.confidence_score
    state["node_results"] = [
        *state.get("node_results", []),
        _ok_node_result("budget_parser", bom_items, confidence=result.confidence_score),
    ]
    state["messages"].append(
        AIMessage(content=f"N9 budget_parser: {len(bom_items)} BOM items extracted")
    )
    return state


# ---------------------------------------------------------------------------
# N10 — Knowledge Graph Builder
# ---------------------------------------------------------------------------

async def knowledge_graph_builder_node(state: ProjectState) -> ProjectState:
    """N10 — Build a project knowledge graph from analysis results."""
    project_id = state.get("project_id")
    tenant_id = state.get("tenant_id")

    if not project_id or not tenant_id:
        state["knowledge_graph_nodes"] = []
        state["knowledge_graph_edges"] = []
        state["messages"].append(
            AIMessage(content="N10 knowledge_graph: skipped (missing project/tenant)")
        )
        return state

    try:
        from src.analysis.adapters.graph.knowledge_graph import KnowledgeGraphAdapter
        from src.analysis.application.build_project_knowledge_graph_use_case import (
            BuildProjectKnowledgeGraphUseCase,
        )

        adapter = KnowledgeGraphAdapter()
        use_case = BuildProjectKnowledgeGraphUseCase(knowledge_graph=adapter)
        graph = await use_case.execute(project_id=UUID(project_id), tenant_id=UUID(tenant_id))
        nodes = [{"id": str(n), "data": graph.nodes[n]} for n in graph.nodes]
        edges = [
            {"source": str(u), "target": str(v), "data": graph.edges[u, v]}
            for u, v in graph.edges
        ]
    except Exception as exc:
        logger.warning("node_knowledge_graph_builder_failed", exc_info=True)
        node_result = _failed_node_result("knowledge_graph", exc)
        await _maybe_await(_persist_node_error(state, node_result))
        nodes = []
        edges = []
        state["knowledge_graph_nodes"] = nodes
        state["knowledge_graph_edges"] = edges
        state["messages"].append(
            AIMessage(content="N10 knowledge_graph: failed (see node_results)")
        )
        state["node_results"] = [*state.get("node_results", []), node_result]
        return state

    state["knowledge_graph_nodes"] = nodes
    state["knowledge_graph_edges"] = edges
    state["node_results"] = [
        *state.get("node_results", []),
        _ok_node_result("knowledge_graph", {"nodes": nodes, "edges": edges}),
    ]
    state["messages"].append(
        AIMessage(content=f"N10 knowledge_graph: {len(nodes)} nodes, {len(edges)} edges")
    )
    return state


# ---------------------------------------------------------------------------
# N11 — Decision Intelligence (delegates to DecisionPackageAssemblyService)
# ---------------------------------------------------------------------------

async def decision_intelligence_node(state: ProjectState) -> ProjectState:
    """N11 — Assemble decision package via DecisionPackageAssemblyService."""
    from src.analysis.domain.report_assembly import (
        DecisionPackageAssemblyService,
        DecisionPackageInput,
    )

    package = DecisionPackageAssemblyService().assemble(
        DecisionPackageInput(
            coherence_score=state.get("coherence_score", 0),
            extracted_risks=state.get("extracted_risks", []),
            extracted_stakeholders=state.get("extracted_stakeholders", []),
            extracted_wbs=state.get("extracted_wbs", []),
            bom_items=state.get("bom_items", []),
            citations=state.get("citations", []),
            citation_validation_passed=state.get("citation_validation_passed", False),
            human_feedback=state.get("human_feedback", ""),
        )
    )

    state["decision_package"] = package
    state["messages"].append(AIMessage(content="N11 decision_intelligence: package assembled"))
    logger.info(
        "node_decision_intelligence",
        project_id=state.get("project_id"),
        coherence_score=package["coherence_score"],
    )
    return state


# ---------------------------------------------------------------------------
# N15 — Citation Validator
# ---------------------------------------------------------------------------

async def citation_validator_node(state: ProjectState) -> dict[str, Any]:
    """TS-UA-ANA-GRAPH-001 - N15 validates citations with branch-local graph updates."""
    from src.analysis.domain.citation_validation import CitationValidatorService

    text = state.get("anonymized_text") or state["document_text"]
    risks = state.get("extracted_risks", [])
    wbs_items = state.get("extracted_wbs", [])

    validation = CitationValidatorService().validate(text, risks, wbs_items)

    citations = [
        Citation(
            type=c.type,
            item=c.item,
            quote=c.quote,
            found_in_source=c.found_in_source,
        ).model_dump(mode="python")
        for c in validation.citations
    ]

    return {
        "citations": citations,
        "citation_validation_passed": validation.validation_passed,
        "messages": [
            AIMessage(
                content=f"N15 citation_validator: {validation.validated_count}/{validation.total_count} "
                f"citations verified, passed={validation.validation_passed}"
            )
        ],
    }


# ---------------------------------------------------------------------------
# N16 — Final Assembler (delegates to ReportAssemblyService)
# ---------------------------------------------------------------------------

async def final_assembler_node(state: ProjectState) -> ProjectState:
    """N16 — Assemble final report via ReportAssemblyService."""
    from src.analysis.domain.report_assembly import ReportAssemblyService, ReportInput

    report = ReportAssemblyService().assemble(
        ReportInput(
            project_id=state.get("project_id", ""),
            document_id=state.get("document_id", ""),
            doc_type=state.get("doc_type", ""),
            document_category=state.get("document_category", ""),
            analysis_id=state.get("analysis_id"),
            extracted_risks=state.get("extracted_risks", []),
            extracted_wbs=state.get("extracted_wbs", []),
            extracted_stakeholders=state.get("extracted_stakeholders", []),
            bom_items=state.get("bom_items", []),
            coherence_score=state.get("coherence_score", 0),
            confidence_score=state.get("confidence_score", 0.0),
            citation_validation_passed=state.get("citation_validation_passed", False),
            pii_redactions=state.get("pii_redactions", []),
            raci_matrix=state.get("raci_matrix", []),
            coherence_breakdown=state.get("coherence_breakdown", {}),
            citations=state.get("citations", []),
            knowledge_graph_nodes=state.get("knowledge_graph_nodes", []),
            knowledge_graph_edges=state.get("knowledge_graph_edges", []),
            decision_package=state.get("decision_package", {}),
            human_approval_required=state.get("human_approval_required", False),
            human_feedback=state.get("human_feedback", ""),
        )
    )

    state["final_report"] = report
    state["messages"].append(
        AIMessage(
            content=(
                f"N16 final_assembler: report assembled — "
                f"{report['summary']['total_risks']} risks, "
                f"{report['summary']['total_wbs_items']} WBS, "
                f"coherence={report['summary']['coherence_score']}"
            )
        )
    )
    logger.info("node_final_assembler", project_id=state.get("project_id"), summary=report["summary"])
    return state
