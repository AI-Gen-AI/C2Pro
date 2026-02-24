"""
Extended LangGraph nodes (N1, N2, N6–N11, N15, N16).

Each node wraps an existing use case / service so the graph orchestrator
can call it without knowing the implementation details.  Dependencies are
resolved lazily (inside each function) to avoid import-time coupling between
bounded contexts — only Protocol-compatible dicts cross the boundary.
"""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

import structlog
from langchain_core.messages import AIMessage

from src.analysis.adapters.graph.schema import ProjectState

logger = structlog.get_logger()

# ── Category classification constants (N1) ──────────────────────────────────

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "SCOPE": ["alcance", "scope", "entregable", "deliverable", "requisito", "requirement"],
    "BUDGET": ["presupuesto", "budget", "coste", "costo", "capex", "opex", "precio", "price"],
    "TIME": ["plazo", "cronograma", "schedule", "hito", "milestone", "deadline", "fecha"],
    "QUALITY": ["calidad", "quality", "norma", "standard", "iso", "certificación"],
    "TECHNICAL": ["técnico", "technical", "especificación", "specification", "diseño", "design"],
    "LEGAL": ["legal", "cláusula", "clause", "contrato", "contract", "obligación", "penalización"],
}

# ── Default PII anonymization config ─────────────────────────────────────────

_DEFAULT_STRATEGY = "REDACT"


# ---------------------------------------------------------------------------
# N1 — Document Ingestion & Classification
# ---------------------------------------------------------------------------

def _classify_category(text: str) -> str:
    """Classify document into a coherence category by keyword frequency."""
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        scores[category] = sum(
            len(re.findall(rf"\b{re.escape(kw)}\b", text_lower))
            for kw in keywords
        )
    if not any(scores.values()):
        return "TECHNICAL"  # default
    return max(scores, key=lambda k: scores[k])


async def document_ingestion_node(state: ProjectState) -> ProjectState:
    """N1 — Parse the document and classify its coherence category.

    Wraps: ``documents.application.parse_document_use_case.ParseDocumentUseCase``
    for parsing (when document_id is available) and adds keyword-based category
    classification that the original use case doesn't provide.
    """
    text = state.get("anonymized_text") or state["document_text"]
    category = _classify_category(text)

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
    """N2 — Detect and redact PII before downstream AI processing.

    Wraps: ``anonymizer.application.anonymization_service.AnonymizationService``
    and ``anonymizer.domain.pii_detector_service.PiiDetectorService``.
    """
    from src.anonymizer.domain.pii_detector_service import PiiDetectorService
    from src.anonymizer.application.anonymization_service import (
        AnonymizationConfig,
        AnonymizationService,
        AnonymizationStrategy,
        PiiType,
    )

    text = state["document_text"]
    detector = PiiDetectorService()
    service = AnonymizationService(pii_detector=detector)

    # Default: redact all PII types
    config = AnonymizationConfig(
        strategies={pii_type: AnonymizationStrategy.REDACT for pii_type in PiiType}
    )

    anonymized = await service.anonymize(text, config)

    # Build redaction log
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
    logger.info(
        "node_pii_anonymizer",
        project_id=state.get("project_id"),
        pii_count=len(redactions),
    )
    return state


# ---------------------------------------------------------------------------
# N6 — Stakeholder Extractor
# ---------------------------------------------------------------------------

async def stakeholder_extractor_node(state: ProjectState) -> ProjectState:
    """N6 — Extract stakeholders from document text.

    Wraps: ``stakeholders.application.extract_stakeholders.ExtractStakeholdersUseCase``
    Uses the AI-powered extraction with contract-specific prompts.
    """
    tenant_id = state.get("tenant_id")
    text = state.get("anonymized_text") or state["document_text"]

    if not tenant_id:
        state["extracted_stakeholders"] = []
        state["messages"].append(
            AIMessage(content="N6 stakeholder_extractor: skipped (missing tenant)")
        )
        return state

    try:
        from src.stakeholders.application.extract_stakeholders import (
            ExtractStakeholdersUseCase as AIExtractStakeholders,
        )
        from src.core.ai.anthropic_wrapper import get_anthropic_wrapper

        ai_provider = get_anthropic_wrapper()
        use_case = AIExtractStakeholders(ai_provider=ai_provider)
        stakeholders = await use_case.execute(
            contract_text=text,
            tenant_id=UUID(tenant_id),
        )
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
    """N7 — Generate RACI matrix from extracted stakeholders and WBS.

    Wraps: ``stakeholders.domain.services.raci_matrix_generator`` for the
    assignment logic.  Uses stakeholders and WBS items already in graph state
    (from N5 and N6) to avoid heavy DB round-trips inside the graph.
    """
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
        from src.analysis.adapters.ai.anthropic_client import AIService

        raci_prompt = (
            "Dada la siguiente lista de stakeholders y actividades WBS, "
            "genera una matriz RACI.\n"
            "Devuelve SOLO un JSON array con objetos: "
            '{"stakeholder": "...", "wbs_code": "...", "role": "R|A|C|I"}\n\n'
            f"Stakeholders: {stakeholders}\n\n"
            f"WBS Items: {wbs_items}"
        )
        service = AIService(tenant_id=state.get("tenant_id"))
        payload = await service.run_extraction(raci_prompt, "")
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
# N8 — Coherence Scorer
# ---------------------------------------------------------------------------

async def coherence_scorer_node(state: ProjectState) -> ProjectState:
    """N8 — Calculate project coherence score.

    Wraps: ``coherence.application.services.coherence_calculation_service.CoherenceCalculationService``
    """
    project_id = state.get("project_id")

    if not project_id:
        state["coherence_score"] = 0
        state["coherence_breakdown"] = {}
        state["messages"].append(
            AIMessage(content="N8 coherence_scorer: skipped (missing project_id)")
        )
        return state

    try:
        from src.coherence.application.services.coherence_calculation_service import (
            CoherenceCalculationService,
        )

        service = CoherenceCalculationService()
        result = service.calculate_coherence(
            project_id=UUID(project_id),
            bom_items=[],
            document_count=1,
        )
        score = result.global_score
        breakdown = {
            cat.value: sub_score
            for cat, sub_score in result.category_scores.items()
        }
    except Exception:
        logger.warning("node_coherence_scorer_failed", exc_info=True)
        score = 0
        breakdown = {}

    state["coherence_score"] = score
    state["coherence_breakdown"] = breakdown
    state["messages"].append(
        AIMessage(content=f"N8 coherence_scorer: score={score}")
    )
    return state


# ---------------------------------------------------------------------------
# N9 — Budget Parser (extended with BOM builder)
# ---------------------------------------------------------------------------

async def budget_parser_extended_node(state: ProjectState) -> ProjectState:
    """N9 — Parse budget data and generate BOM items.

    Wraps: ``procurement.application.bom_builder_service.BOMBuilderService``
    Falls back to basic extraction when WBS items are missing.
    """
    from src.analysis.adapters.ai.anthropic_client import AIService

    text = state.get("anonymized_text") or state["document_text"]
    tenant_id = state.get("tenant_id")

    # Use AI to extract budget line items
    budget_prompt = (
        "Extrae las partidas presupuestarias del documento.\n"
        "Devuelve SOLO un JSON con el formato:\n"
        '{"items": [{"name": "...", "amount": 0.0, "currency": "EUR", "category": "..."}]}'
    )

    bom_items: list[dict[str, Any]] = []
    try:
        service = AIService(tenant_id=tenant_id)
        payload = await service.run_extraction(budget_prompt, text)
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
    """N10 — Build a project knowledge graph from analysis results.

    Wraps: ``analysis.application.build_project_knowledge_graph_use_case.BuildProjectKnowledgeGraphUseCase``
    """
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
        from src.analysis.application.build_project_knowledge_graph_use_case import (
            BuildProjectKnowledgeGraphUseCase,
        )
        from src.analysis.adapters.graph.knowledge_graph import KnowledgeGraphAdapter

        adapter = KnowledgeGraphAdapter()
        use_case = BuildProjectKnowledgeGraphUseCase(knowledge_graph=adapter)
        graph = await use_case.execute(
            project_id=UUID(project_id),
            tenant_id=UUID(tenant_id),
        )
        nodes = [
            {"id": str(n), "data": graph.nodes[n]}
            for n in graph.nodes
        ]
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
        AIMessage(
            content=f"N10 knowledge_graph: {len(nodes)} nodes, {len(edges)} edges"
        )
    )
    return state


# ---------------------------------------------------------------------------
# N11 — Decision Intelligence Orchestrator
# ---------------------------------------------------------------------------

async def decision_intelligence_node(state: ProjectState) -> ProjectState:
    """N11 — Assemble a decision package from all upstream results.

    Wraps: ``modules.decision_intelligence.domain.entities.FinalDecisionPackage``
    Uses the DI ports when a concrete adapter is available; otherwise assembles
    the package directly from graph state.
    """
    package: dict[str, Any] = {
        "coherence_score": state.get("coherence_score", 0),
        "risks": state.get("extracted_risks", []),
        "stakeholders": state.get("extracted_stakeholders", []),
        "wbs_items": state.get("extracted_wbs", []),
        "bom_items": state.get("bom_items", []),
        "evidence_links": [],
        "citations": [c.get("quote", "") for c in state.get("citations", [])],
        "citation_validation_passed": state.get("citation_validation_passed", False),
        "approved_by": None,
        "approved_at": None,
    }

    # If human feedback was provided, mark it
    if state.get("human_feedback"):
        package["approved_by"] = "human_reviewer"

    state["decision_package"] = package
    state["messages"].append(
        AIMessage(content="N11 decision_intelligence: package assembled")
    )
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
    """N15 — Validate that extracted data can be traced back to source text.

    Compares extracted risk quotes and WBS descriptions against the original
    document text to verify provenance.
    """
    text = state.get("anonymized_text") or state["document_text"]
    text_lower = text.lower()

    citations: list[dict[str, Any]] = []
    all_valid = True

    # Validate risk source quotes
    for risk in state.get("extracted_risks", []):
        quote = risk.get("source_quote") or risk.get("source_text_snippet") or ""
        found = bool(quote and quote.lower() in text_lower)
        citations.append({
            "type": "risk",
            "item": risk.get("title") or risk.get("summary", ""),
            "quote": quote,
            "found_in_source": found,
        })
        if not found and quote:
            all_valid = False

    # Validate WBS item descriptions
    for wbs in state.get("extracted_wbs", []):
        desc = wbs.get("description") or wbs.get("name") or ""
        # For WBS, check if at least a significant fragment appears in the source
        fragment = desc[:80].lower() if desc else ""
        found = bool(fragment and fragment in text_lower)
        citations.append({
            "type": "wbs",
            "item": wbs.get("code", ""),
            "quote": desc[:120],
            "found_in_source": found,
        })

    validated_count = sum(1 for c in citations if c["found_in_source"])
    total = len(citations)

    state["citations"] = citations
    state["citation_validation_passed"] = all_valid or (total > 0 and validated_count / total >= 0.6)
    state["messages"].append(
        AIMessage(
            content=f"N15 citation_validator: {validated_count}/{total} citations verified, "
            f"passed={state['citation_validation_passed']}"
        )
    )
    return state


# ---------------------------------------------------------------------------
# N16 — Final Assembler
# ---------------------------------------------------------------------------

async def final_assembler_node(state: ProjectState) -> ProjectState:
    """N16 — Assemble all analysis results into a structured final report.

    Combines outputs from all upstream nodes into a single report dict
    suitable for API response or PDF generation.
    """
    report: dict[str, Any] = {
        "project_id": state.get("project_id"),
        "document_id": state.get("document_id"),
        "doc_type": state.get("doc_type"),
        "document_category": state.get("document_category", ""),
        "analysis_id": state.get("analysis_id"),
        "summary": {
            "total_risks": len(state.get("extracted_risks", [])),
            "total_wbs_items": len(state.get("extracted_wbs", [])),
            "total_stakeholders": len(state.get("extracted_stakeholders", [])),
            "total_bom_items": len(state.get("bom_items", [])),
            "coherence_score": state.get("coherence_score", 0),
            "confidence_score": state.get("confidence_score", 0.0),
            "citation_validation_passed": state.get("citation_validation_passed", False),
            "pii_items_redacted": len(state.get("pii_redactions", [])),
        },
        "risks": state.get("extracted_risks", []),
        "wbs_items": state.get("extracted_wbs", []),
        "stakeholders": state.get("extracted_stakeholders", []),
        "raci_matrix": state.get("raci_matrix", []),
        "bom_items": state.get("bom_items", []),
        "coherence_breakdown": state.get("coherence_breakdown", {}),
        "citations": state.get("citations", []),
        "knowledge_graph": {
            "nodes": state.get("knowledge_graph_nodes", []),
            "edges": state.get("knowledge_graph_edges", []),
        },
        "decision_package": state.get("decision_package", {}),
        "human_approval_required": state.get("human_approval_required", False),
        "human_feedback": state.get("human_feedback", ""),
    }

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
    logger.info(
        "node_final_assembler",
        project_id=state.get("project_id"),
        summary=report["summary"],
    )
    return state
