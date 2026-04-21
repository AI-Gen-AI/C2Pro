"""
Pure domain services for AI-backed extraction steps.

Each service encapsulates a single AI call (or deterministic rule-based
equivalent) and knows nothing about LangGraph, workflow state, or the
ProjectState TypedDict. The services depend on an `AIExtractionPort`
protocol that any adapter can satisfy.

Refers to EPIC-CORE-DECOUPLE / TASK-IMPL-010 Phase 1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

from src.analysis.domain.prompts import (
    BUDGET_EXTRACTION_PROMPT,
    CRITIQUE_SYSTEM_PROMPT,
    DOC_TYPES,
    RACI_GENERATION_PROMPT,
    ROUTER_SYSTEM_PROMPT,
)


class AIExtractionPort(Protocol):
    """Outbound port — adapters satisfy this (e.g. `AIService.run_extraction`)."""

    async def run_extraction(self, system_prompt: str, user_content: str) -> Any: ...


# ── Document Type Classification (N3) ────────────────────────────────────────


def _fallback_doc_type(text: str) -> str:
    low = text.lower()
    if any(k in low for k in ("contrato", "clausula", "contract", "clause", "obligaciones")):
        return "contract"
    if any(k in low for k in ("presupuesto", "capex", "opex", "budget", "cost")):
        return "budget"
    if any(k in low for k in ("cronograma", "plazo", "hito", "schedule", "milestone", "gantt")):
        return "schedule"
    return "technical_spec"


@dataclass(frozen=True)
class DocumentTypeClassificationService:
    """Classify a document into one of `DOC_TYPES` via AI with keyword fallback."""

    async def classify(self, *, text: str, ai: AIExtractionPort) -> str:
        try:
            payload = await ai.run_extraction(ROUTER_SYSTEM_PROMPT, text)
            if isinstance(payload, dict):
                candidate = str(payload.get("doc_type", "")).strip().lower()
                if candidate in DOC_TYPES:
                    return candidate
        except Exception:
            pass
        return _fallback_doc_type(text)


# ── Critique Extraction (N12) ────────────────────────────────────────────────


@dataclass(frozen=True)
class CritiqueResult:
    status: str  # "OK" | "RETRY"
    notes: str


@dataclass(frozen=True)
class CritiqueExtractionService:
    """Ask the LLM to critique extraction quality; returns normalized result."""

    async def extract(
        self,
        *,
        items: list[dict[str, Any]],
        doc_type: str,
        ai: AIExtractionPort,
    ) -> CritiqueResult:
        try:
            payload = await ai.run_extraction(
                CRITIQUE_SYSTEM_PROMPT,
                f"Document type: {doc_type}\nExtraction results: {items}",
            )
            if isinstance(payload, dict):
                status = str(payload.get("status", "")).upper()
                notes = str(payload.get("notes", "")).strip()
                if status in {"OK", "RETRY"}:
                    return CritiqueResult(status=status, notes=notes)
        except Exception:
            pass
        return CritiqueResult(status="RETRY", notes="Automatic critique inconclusive.")


# ── RACI Matrix Generation (N7) ──────────────────────────────────────────────


@dataclass(frozen=True)
class RaciGenerationService:
    """Generate a RACI matrix from stakeholders + WBS via LLM."""

    async def generate(
        self,
        *,
        stakeholders: list[dict[str, Any]],
        wbs_items: list[dict[str, Any]],
        ai: AIExtractionPort,
    ) -> list[dict[str, Any]]:
        prompt = (
            f"{RACI_GENERATION_PROMPT}\n\n"
            f"Stakeholders: {stakeholders}\n\n"
            f"WBS Items: {wbs_items}"
        )
        payload = await ai.run_extraction(prompt, "")
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and "assignments" in payload:
            assignments = payload["assignments"]
            return assignments if isinstance(assignments, list) else [assignments]
        return [payload] if payload else []


# ── Budget / BOM Extraction (N9) ─────────────────────────────────────────────


@dataclass(frozen=True)
class BudgetExtractionService:
    """Extract normalized BOM items from a budget-oriented document."""

    async def extract_bom(
        self,
        *,
        text: str,
        ai: AIExtractionPort,
    ) -> list[dict[str, Any]]:
        payload = await ai.run_extraction(BUDGET_EXTRACTION_PROMPT, text)
        if not isinstance(payload, dict):
            return []
        raw_items = payload.get("items", [])
        return [
            {
                "name": item.get("name", "Unknown"),
                "amount": item.get("amount", 0.0),
                "currency": item.get("currency", "EUR"),
                "category": item.get("category", "general"),
            }
            for item in raw_items
            if isinstance(item, dict)
        ]


# ── Deterministic Rule-Based Extractors (N4/N5 mock mode) ────────────────────


@dataclass(frozen=True)
class DeterministicRiskRulesService:
    """Pure keyword-rule extractor used by N4 mock mode & offline tests."""

    def extract(self, text: str) -> list[dict[str, Any]]:
        risks: list[dict[str, Any]] = []
        lower = text.lower()
        if "penalt" in lower or "% for delay" in lower or "delay" in lower:
            risks.append(
                {
                    "category": "LEGAL",
                    "title": "Delay penalty exposure",
                    "summary": "Contract includes delay penalties.",
                    "description": "The contract contains penalty language linked to delay or late completion.",
                    "probability": "MEDIUM",
                    "impact": "HIGH",
                    "mitigation_suggestion": "Validate schedule buffers, milestone logic, and penalty caps before execution.",
                    "source_quote": "Daily penalty 2% for delay.",
                    "source_text_snippet": "Daily penalty 2% for delay.",
                    "risk_score": 6,
                    "immediate_alert": False,
                    "confidence": 0.82,
                }
            )
        if re.search(r"\b30\s+days\b", lower) and "payment" in lower:
            risks.append(
                {
                    "category": "FINANCIAL",
                    "title": "Payment term cash-flow risk",
                    "summary": "Payment depends on certified milestones within a defined term.",
                    "description": "Cash flow may depend on milestone certification and payment timing discipline.",
                    "probability": "MEDIUM",
                    "impact": "MEDIUM",
                    "mitigation_suggestion": "Check certification workflow, invoice timing, and interim financing assumptions.",
                    "source_quote": "Payment subject to certified milestones within 30 days.",
                    "source_text_snippet": "Payment subject to certified milestones within 30 days.",
                    "risk_score": 4,
                    "immediate_alert": False,
                    "confidence": 0.79,
                }
            )
        if "warranty" in lower:
            risks.append(
                {
                    "category": "QUALITY",
                    "title": "Warranty obligation exposure",
                    "summary": "Warranty obligations extend post-handover liability.",
                    "description": "The contract imposes a warranty period that may require post-completion corrections.",
                    "probability": "MEDIUM",
                    "impact": "MEDIUM",
                    "mitigation_suggestion": "Confirm defect response process, retention terms, and warranty reserve assumptions.",
                    "source_quote": "Warranty period is 24 months.",
                    "source_text_snippet": "Warranty period is 24 months.",
                    "risk_score": 4,
                    "immediate_alert": False,
                    "confidence": 0.77,
                }
            )
        return risks


@dataclass(frozen=True)
class DeterministicWbsRulesService:
    """Pure keyword-rule WBS extractor used by N5 mock mode & offline tests."""

    def extract(self, text: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        lower = text.lower()
        if any(term in lower for term in ["scope", "works", "materials", "inspection", "handover"]):
            items.append(
                {
                    "code": "1.1",
                    "name": "Contract scope execution",
                    "description": "Execution of the contract scope including materials, inspection, testing, and handover.",
                    "item_type": "work_package",
                    "confidence": 0.8,
                }
            )
        if "deadline" in lower or "completion" in lower:
            items.append(
                {
                    "code": "1.2",
                    "name": "Completion milestone control",
                    "description": "Control of delivery and completion milestones against contractual dates.",
                    "item_type": "activity",
                    "confidence": 0.78,
                }
            )
        return items
