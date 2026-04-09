"""
Extended LangGraph nodes (N1, N2, N6–N11, N15, N16).

Thin adapter wrappers — business logic lives in domain services and
application use cases. Dependencies resolved lazily to avoid import-time
coupling between bounded contexts.

Refers to TASK-IMPL-010.8–.14 (node refactoring).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from langchain_core.messages import AIMessage

from src.analysis.adapters.graph.dependencies import (
    get_ai_service,
    get_anonymization_service,
    get_pii_detector_service,
)
from src.analysis.adapters.graph.schema import ProjectState
from src.analysis.domain.document_classification import DocumentCategoryClassifier
from src.analysis.domain.prompts import BUDGET_EXTRACTION_PROMPT, RACI_GENERATION_PROMPT

logger = structlog.get_logger()

# ── Domain service instances (stateless, reusable) ──────────────────────────

_document_classifier = DocumentCategoryClassifier()


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

async def stakeholder_extractor_node(state: ProjectState) -> ProjectState:
    """N6 — Extract stakeholders from document text."""
    tenant_id = state.get("tenant_id")
    text = state.get("anonymized_text") or state["document_text"]

    if not tenant_id:
        state["extracted_stakeholders"] = []
        state["messages"].append(
            AIMessage(content="N6 stakeholder_extractor: skipped (missing tenant)")
        )
        return state

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

    state["extracted_stakeholders"] = result
    state["messages"].append(
        AIMessage(content=f"N6 stakeholder_extractor: {len(result)} stakeholders found")
    )
    return state


# ---------------------------------------------------------------------------
# N7 — RACI Generator
# ---------------------------------------------------------------------------

async def raci_generator_node(state: ProjectState) -> ProjectState:
    """N7 — Generate RACI matrix from extracted stakeholders and WBS."""
    stakeholders = state.get("extracted_stakeholders", [])
    wbs_items = state.get("extracted_wbs", [])

    if not stakeholders or not wbs_items:
        state["raci_matrix"] = []
        state["messages"].append(
            AIMessage(
                content=(
                    f"N7 raci_generator: skipped "
                    f"(stakeholders={len(stakeholders)}, wbs={len(wbs_items)})"
                )
            )
        )
        return state

    try:
        prompt = (
            f"{RACI_GENERATION_PROMPT}\n\n"
            f"Stakeholders: {stakeholders}\n\n"
            f"WBS Items: {wbs_items}"
        )
        service = get_ai_service(state.get("tenant_id"))
        payload = await service.run_extraction(prompt, "")
        if isinstance(payload, list):
            matrix = payload
        elif isinstance(payload, dict) and "assignments" in payload:
            matrix = payload["assignments"]
        else:
            matrix = [payload] if payload else []
    except Exception:
        logger.warning("node_raci_generator_failed", exc_info=True)
        matrix = []

    state["raci_matrix"] = matrix if isinstance(matrix, list) else [matrix]
    state["messages"].append(
        AIMessage(content=f"N7 raci_generator: {len(state['raci_matrix'])} assignments generated")
    )
    return state


# ---------------------------------------------------------------------------
# N8 — Coherence Scorer (delegates to ScoreFromExtractionUseCase)
# ---------------------------------------------------------------------------

async def coherence_scorer_node(state: ProjectState) -> ProjectState:
    """N8 — Calculate Coherence Score via ScoreFromExtractionUseCase."""
    project_id = state.get("project_id")

    if not project_id:
        state["coherence_score"] = 0
        state["coherence_breakdown"] = {}
        state["messages"].append(
            AIMessage(content="N8 coherence_scorer: skipped (missing project_id)")
        )
        return state

    try:
        from src.analysis.domain.coherence_derivation import CoherenceScoringDerivationService
        from src.coherence.application.dependencies import build_coherence_calculation_service
        from src.coherence.application.use_cases.score_from_extraction import (
            ScoreFromExtractionCommand,
            ScoreFromExtractionUseCase,
        )

        result = ScoreFromExtractionUseCase(
            derivation_service=CoherenceScoringDerivationService(),
            calculation_service=build_coherence_calculation_service(),
        ).execute(
            ScoreFromExtractionCommand(
                project_id=UUID(project_id),
                extracted_risks=state.get("extracted_risks", []),
                extracted_wbs=state.get("extracted_wbs", []),
                bom_items=state.get("bom_items", []),
                confidence_score=state.get("confidence_score", 0.0),
                document_text=state.get("document_text", ""),
            )
        )
        score = result.score
        breakdown = result.breakdown
        quality_note = result.quality_note
    except Exception:
        logger.warning("node_coherence_scorer_failed", exc_info=True)
        score = 0
        breakdown = {}
        quality_note = ""

    risk_count = len(state.get("extracted_risks", []))
    wbs_count = len(state.get("extracted_wbs", []))

    state["coherence_score"] = score
    state["coherence_breakdown"] = breakdown
    state["messages"].append(
        AIMessage(
            content=f"N8 coherence_scorer: score={score} "
            f"(derived from {risk_count} risks, {wbs_count} WBS items{quality_note})"
        )
    )
    return state


# ---------------------------------------------------------------------------
# N9 — Budget Parser (extended with BOM builder)
# ---------------------------------------------------------------------------

async def budget_parser_extended_node(state: ProjectState) -> ProjectState:
    """N9 — Parse budget data and generate BOM items."""
    text = state.get("anonymized_text") or state["document_text"]
    tenant_id = state.get("tenant_id")

    bom_items: list[dict[str, Any]] = []
    try:
        service = get_ai_service(tenant_id)
        payload = await service.run_extraction(BUDGET_EXTRACTION_PROMPT, text)
        if isinstance(payload, dict):
            raw_items = payload.get("items", [])
            bom_items = [
                {
                    "name": item.get("name", "Unknown"),
                    "amount": item.get("amount", 0.0),
                    "currency": item.get("currency", "EUR"),
                    "category": item.get("category", "general"),
                }
                for item in raw_items
                if isinstance(item, dict)
            ]
    except Exception:
        logger.warning("node_budget_parser_extended_failed", exc_info=True)

    state["bom_items"] = bom_items
    state["extracted_wbs"] = state.get("extracted_wbs") or []
    state["confidence_score"] = 0.7 if bom_items else 0.0
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

async def citation_validator_node(state: ProjectState) -> ProjectState:
    """N15 — Validate that extracted data can be traced back to source text."""
    from src.analysis.domain.citation_validation import CitationValidatorService

    text = state.get("anonymized_text") or state["document_text"]
    risks = state.get("extracted_risks", [])
    wbs_items = state.get("extracted_wbs", [])

    validation = CitationValidatorService().validate(text, risks, wbs_items)

    citations = [
        {"type": c.type, "item": c.item, "quote": c.quote, "found_in_source": c.found_in_source}
        for c in validation.citations
    ]

    state["citations"] = citations
    state["citation_validation_passed"] = validation.validation_passed
    state["messages"].append(
        AIMessage(
            content=f"N15 citation_validator: {validation.validated_count}/{validation.total_count} "
            f"citations verified, passed={validation.validation_passed}"
        )
    )
    return state


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
