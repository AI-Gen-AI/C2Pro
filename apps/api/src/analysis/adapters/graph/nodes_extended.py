"""
Extended LangGraph nodes (N1, N2, N6–N11, N15, N16).

Thin adapter wrappers — business logic lives in domain services and
application use cases. Dependencies resolved lazily to avoid import-time
coupling between bounded contexts.

Refers to TASK-IMPL-010.8–.14 (node refactoring).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from langchain_core.messages import AIMessage

from src.analysis.adapters.graph.dependencies import (
    get_ai_service,
    get_anonymization_service,
    get_pii_detector_service,
)
from src.analysis.adapters.graph.schema import ProjectState
from src.analysis.application.generate_raci_use_case import (
    GenerateRaciCommand,
    GenerateRaciUseCase,
)
from src.analysis.application.parse_budget_use_case import (
    ParseBudgetCommand,
    ParseBudgetUseCase,
)
from src.analysis.domain.document_classification import DocumentCategoryClassifier

logger = structlog.get_logger()

if TYPE_CHECKING:
    from src.coherence.models import Clause

# ── Domain service instances (stateless, reusable) ──────────────────────────

_document_classifier = DocumentCategoryClassifier()
MIN_EXTRACTABLE_TEXT_CHARS = 8


def _meaningful_text_length(text: str | None) -> int:
    return len("".join((text or "").split()))


def _has_extractable_text(text: str | None) -> bool:
    return _meaningful_text_length(text) >= MIN_EXTRACTABLE_TEXT_CHARS


def _insufficient_extractable_text_message() -> str:
    return "No extractable text — document may be scanned; OCR required"


# ---------------------------------------------------------------------------
# N1 — Document Ingestion & Classification
# ---------------------------------------------------------------------------


async def document_ingestion_node(state: ProjectState) -> ProjectState:
    """N1 — Parse the document and classify its coherence category."""
    text = state.get("anonymized_text") or state["document_text"]
    if not _has_extractable_text(text):
        state["document_parsed"] = False
        state["document_category"] = "insufficient_extractable_text"
        state["messages"].append(AIMessage(content=_insufficient_extractable_text_message()))
        logger.warning(
            "node_document_ingestion_insufficient_extractable_text",
            project_id=state.get("project_id"),
            document_id=state.get("document_id"),
            meaningful_chars=_meaningful_text_length(text),
            threshold=MIN_EXTRACTABLE_TEXT_CHARS,
        )
        return state

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
        return {
            "extracted_stakeholders": [],
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
    except Exception:
        logger.warning("node_stakeholder_extractor_failed", exc_info=True)
        result = []

    return {
        "extracted_stakeholders": result,
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
        return {
            "coherence_score": None,
            "coherence_breakdown": {},
            "coherence_reason": "missing_project_id",
            "coherence_missing_dimensions": ["schedule", "budget"],
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
        result = await evaluate_coherence_async(
            clauses=clauses,
            project_id=project_id,
            config=EvaluationConfig(
                low_budget_mode=True,
                tenant_id=state.get("tenant_id"),
                project_id=project_id,
                poor_extraction_quality=derivation.poor_extraction_quality,
                missing_dimensions=missing_dimensions,
            ),
        )
        score = result.overall_score
        breakdown: dict[str, Any] = {
            item.category: item.score
            for item in result.category_breakdown
        }
        quality_note = derivation.quality_note
        reason = result.score_reason
        result_missing_dimensions = result.score_missing_dimensions or missing_dimensions
    except Exception:
        logger.warning("node_coherence_scorer_failed", exc_info=True)
        score = None
        breakdown = {}
        quality_note = ""
        reason = "coherence_evaluation_failed"
        result_missing_dimensions = ["schedule", "budget"]

    risk_count = len(state.get("extracted_risks", []))
    wbs_count = len(state.get("extracted_wbs", []))

    return {
        "coherence_score": score,
        "coherence_breakdown": breakdown,
        "coherence_reason": reason,
        "coherence_missing_dimensions": result_missing_dimensions,
        "messages": [
            AIMessage(
                content=f"N8 coherence_scorer: score={score} "
                f"(derived from {risk_count} risks, {wbs_count} WBS items{quality_note})"
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

    use_case = ParseBudgetUseCase(ai=get_ai_service(tenant_id))
    result = await use_case.execute(ParseBudgetCommand(text=text))

    state["bom_items"] = result.bom_items
    state["extracted_wbs"] = state.get("extracted_wbs") or []
    state["confidence_score"] = result.confidence_score
    state["messages"].append(
        AIMessage(content=f"N9 budget_parser: {len(result.bom_items)} BOM items extracted")
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
    except Exception:
        logger.warning("node_knowledge_graph_builder_failed", exc_info=True)
        nodes = []
        edges = []

    state["knowledge_graph_nodes"] = nodes
    state["knowledge_graph_edges"] = edges
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
        {"type": c.type, "item": c.item, "quote": c.quote, "found_in_source": c.found_in_source}
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
