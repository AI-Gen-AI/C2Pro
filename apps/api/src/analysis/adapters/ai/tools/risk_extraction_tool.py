"""
analysis/adapters/ai/tools/risk_extraction_tool.py

Extracts contractual and project risks from narrative sections.

Test Suite ID: TS-QA-SWAGGER-ANALYSIS-001
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel, Field

from src.analysis.adapters.ai.agents.risk_extractor import (
    RiskCategory,
    RiskImpact,
    RiskItem,
    RiskProbability,
)
from src.analysis.domain.risk_categories import normalize_category
from src.core.ai.anthropic_wrapper import AIResponse
from src.core.ai.model_router import AITaskType
from src.core.ai.tools import BaseTool, RetryPolicy, ToolResult, register_tool

if TYPE_CHECKING:
    from src.analysis.adapters.graph.schema import ProjectState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Filter configuration — multilingual (ES + EN) and env-tunable.
#
# Background: the filter is applied to the full document text before the LLM
# call. It (1) drops obviously irrelevant paragraphs (price tables, BOMs) and
# (2) selects substantive risk-bearing paragraphs. Until this change the
# keyword lists were Spanish-only, which silently fell through on English
# contracts ("filter matched nothing → use all paragraphs") and then
# truncated to 15000 chars — losing ~37% of even modestly-sized contracts.
# Diagnosis: scripts/diagnose_chunks.py on the live EPC contract.
# ---------------------------------------------------------------------------

_INCLUDE_KEYWORDS_ES: tuple[str, ...] = (
    "condiciones particulares",
    "condiciones especiales",
    "memoria tecnica",
    "memoria del proyecto",
    "alcance",
    "penal",
    "multa",
    "garantia",
    "responsabilidad",
    "retraso",
    "cronograma",
    "ruta critica",
    "dependencia",
    "permisos",
    "aprobacion",
    "geotec",
    "suelo",
    "seguridad",
    "ambiental",
    "calidad",
    "especificacion",
    "ensayo",
    "prueba",
)

_INCLUDE_KEYWORDS_EN: tuple[str, ...] = (
    "particular conditions",
    "general conditions",
    "scope",
    "penalty",
    "liquidated damages",
    "fine",
    "warranty",
    "warranties",
    "liability",
    "liabilities",
    "indemnif",          # indemnify, indemnification, indemnity
    "responsibility",
    "obligation",
    "default",
    "breach",
    "terminate",
    "termination",
    "force majeure",
    "delay",
    "schedule",
    "completion",
    "milestone",
    "critical path",
    "dependency",
    "permit",
    "approval",
    "geotech",
    "soil",
    "safety",
    "environmental",
    "quality",
    "specification",
    "test",
    "commissioning",
    "performance",
    "governing law",
    "dispute",
    "arbitration",
    "insurance",
)

_EXCLUDE_KEYWORDS_ES: tuple[str, ...] = (
    "tabla de precios",
    "precio unitario",
    "medicion y pago",
    "presupuesto",
    "subtotal",
)

_EXCLUDE_KEYWORDS_EN: tuple[str, ...] = (
    "price schedule",
    "unit price",
    "bill of materials",
    "bom",
    "subtotal",
)

_INCLUDE_KEYWORDS: tuple[str, ...] = _INCLUDE_KEYWORDS_ES + _INCLUDE_KEYWORDS_EN
_EXCLUDE_KEYWORDS: tuple[str, ...] = _EXCLUDE_KEYWORDS_ES + _EXCLUDE_KEYWORDS_EN


def _resolve_max_chars() -> int:
    """Read RISK_EXTRACTION_MAX_CHARS env var, with safe defaults.

    The previous hard-coded 15000 was tuned for Claude pre-200K-context
    models. Modern Claude models accept far more — 40000 chars (~10K
    tokens) is still well within any reasonable context budget.
    Configurable so ops can tune per-environment.
    """
    raw = os.getenv("RISK_EXTRACTION_MAX_CHARS")
    if raw is None:
        return 40_000
    try:
        value = int(raw)
    except ValueError:
        logger.warning(
            "risk_extraction_max_chars_invalid",
            extra={"raw_value": raw, "fallback": 40_000},
        )
        return 40_000
    return max(5_000, min(value, 200_000))


class RiskExtractionInput(BaseModel):
    """Input for risk extraction."""

    document_text: str = Field(..., description="Contract text to analyze")
    max_risks: int = Field(20, ge=1, le=50, description="Maximum risks to extract")
    filter_relevant: bool = Field(
        True, description="Apply relevance filtering to document"
    )


@register_tool("risk_extraction", version="1.0")
class RiskExtractionTool(BaseTool[RiskExtractionInput, list[RiskItem]]):
    """
    Extracts contractual and project risks from narrative contract sections.

    Capabilities:
    - Identifies legal, financial, schedule, technical, HSE, and quality risks
    - Assigns probability and impact scores
    - Flags immediate alerts for critical risks
    - Filters out irrelevant sections (pricing tables, BOMs)

    Input: Document text
    Output: List of RiskItem with category, probability, impact, mitigation
    """

    name = "risk_extraction"
    version = "1.0"
    description = "Extracts and scores risks from contract documents"
    task_type = AITaskType.COMPLEX_EXTRACTION
    prompt_template_name = None  # Using inline prompt for now
    retry_policy = RetryPolicy(max_retries=0)

    async def _execute_impl(
        self,
        input_data: RiskExtractionInput,
        tenant_id: UUID | None,
        ai_response: AIResponse,
    ) -> list[RiskItem]:
        """Parse AI response and apply domain logic.

        Note: relevance filtering is applied in ``extract_input_from_state``
        BEFORE the LLM call, not here. Historically the filter ran in this
        method on a local copy that was immediately discarded, so the LLM
        always saw the unfiltered text. That was a latent no-op.
        """
        _ = tenant_id

        # Parse JSON response
        try:
            payload = json.loads(ai_response.content)
        except json.JSONDecodeError:
            # Fallback: try to extract JSON from text
            payload = self._extract_json_from_text(ai_response.content)

        # Extract risk items
        items = self._extract_items(payload)
        if not items and input_data.document_text.strip():
            raise ValueError(
                "No risk items extracted from non-empty contract text. "
                "The model response must include at least one valid risk item."
            )

        # Coerce to RiskItem models with validation
        risks: list[RiskItem] = []
        for item in items:
            risk = self._coerce_risk(item)
            if risk:
                # Apply domain logic
                risk.risk_score = self._calculate_risk_score(risk)
                risk.immediate_alert = self._is_immediate_alert(risk)
                risks.append(risk)
        if not risks and input_data.document_text.strip():
            raise ValueError(
                "No risk items extracted from non-empty contract text. "
                "The model response did not contain any valid risk items."
            )

        # Sort by risk score
        risks.sort(key=lambda r: r.risk_score, reverse=True)

        # Apply max_risks limit
        if len(risks) > input_data.max_risks:
            risks = risks[: input_data.max_risks]

        return risks

    def extract_input_from_state(self, state: ProjectState) -> RiskExtractionInput:
        """Extract input from LangGraph state.

        Applies relevance filtering HERE (pre-LLM) so the prompt actually
        respects the multilingual include/exclude keywords and the
        ``RISK_EXTRACTION_MAX_CHARS`` cap. The augmentation suffixes
        (critique_notes, human_feedback) are appended after filtering so
        they are never stripped — they are always relevant signal.
        """
        doc_text = state["document_text"]
        original_chars = len(doc_text)

        filter_relevant = True
        if filter_relevant:
            filtered = self._filter_relevant_text(doc_text)
            logger.info(
                "risk_extraction_input_prepared",
                extra={
                    "original_chars": original_chars,
                    "filtered_chars": len(filtered),
                    "delta": original_chars - len(filtered),
                },
            )
            doc_text = filtered

        # Augmentation suffixes — keep them OUTSIDE the filter so they
        # always reach the LLM.
        if state.get("critique_notes"):
            doc_text = f"{doc_text}\n\nCRITIQUE: {state['critique_notes']}"

        if state.get("human_feedback"):
            doc_text = f"{doc_text}\n\nFEEDBACK: {state['human_feedback']}"

        return RiskExtractionInput(
            document_text=doc_text,
            max_risks=20,
            filter_relevant=filter_relevant,
        )

    def inject_output_into_state(
        self,
        state: ProjectState,
        result: ToolResult[list[RiskItem]],
    ) -> ProjectState:
        """Inject output into LangGraph state."""
        risks = result.data or []
        state["extracted_risks"] = [self._risk_item_to_dict(risk) for risk in risks]

        if not result.success:
            state["critique_notes"] = result.error or "Risk extraction failed"
            state["confidence_score"] = 0.0
            return state

        # Update confidence score based on result quality
        if result.confidence_score:
            if risks:
                confidences = [item.confidence for item in risks]
                state["confidence_score"] = (
                    sum(confidences) / len(confidences) if confidences else 0.9
                )
            else:
                state["confidence_score"] = 0.9
        else:
            # Calculate average confidence if individual risks have confidence
            confidences = [
                r.get("confidence", 0.9) for r in state["extracted_risks"]
            ]
            state["confidence_score"] = (
                sum(confidences) / len(confidences) if confidences else 0.9
            )

        return state

    def _build_default_prompt(
        self, input_data: RiskExtractionInput, is_retry: bool
    ) -> tuple[str, str | None]:
        """Build prompt for risk extraction.

        Prompt is in English (LLM-native language) per [[reference_model_routing_c2pro]] —
        Spanish prompts on English contracts make Claude generate prose
        instead of strict JSON and hit the output token cap before closing
        the JSON. Output text fields ARE allowed to be in any language;
        what matters is that the JSON envelope and keywords stay machine-
        parseable.
        """
        system_prompt = """
You are a senior project risk analyst for infrastructure contracts (EPC, IPC, EPCM, civil works).

Extract risks from the narrative clauses of the contract. Identify:

- LEGAL risks: obligations, penalties, termination, indemnification, dispute resolution, governing law, force majeure, liability cap, warranty
- BUDGET risks: bank guarantees, liquidated damages, payment terms, advance/retention, price escalation, currency
- SCHEDULE risks: critical deadlines, milestones, dependencies, delay events, effective date conditions
- TECHNICAL risks: specifications, performance tests, geotechnics, interface, commissioning
- QUALITY risks: inspections, standards, factory/site acceptance tests, defects liability, safety, environmental, permits
- SCOPE risks: scope of work, exclusions, responsibilities, interfaces, change management

For each risk, return a JSON object with EXACTLY these keys:

{
  "category": "LEGAL|SCHEDULE|QUALITY|SCOPE|TECHNICAL|BUDGET",
  "title": "Short risk title",
  "summary": "One-sentence summary",
  "description": "Detailed risk description grounded in the cited clause",
  "probability": "LOW|MEDIUM|HIGH",
  "impact": "LOW|MEDIUM|HIGH|CRITICAL",
  "mitigation_suggestion": "Concrete mitigation step",
  "source_quote": "Verbatim multi-sentence excerpt from the contract that substantiates the risk (NOT a section heading or single word — at least 80 chars of real contract text)",
  "source_text_snippet": "Same or longer surrounding context for traceability"
}

CRITICAL OUTPUT RULES:

1. Respond with ONLY a JSON object — no markdown, no prose, no explanations, no code fences.
2. The JSON envelope MUST be exactly: {"risks": [ ... ]}
3. Every risk MUST have all keys above. Omit risks you cannot ground in a verbatim quote.
4. Prefer FEWER, well-grounded risks (3-8) over many superficial ones.
5. source_quote must be ≥80 characters of contract text. NEVER use section labels alone.
""".strip()

        user_prompt = f"CONTRACT:\n\n{input_data.document_text}"

        if is_retry:
            user_prompt = (
                f"{user_prompt}\n\n"
                "REMINDER: Respond with ONLY valid JSON. "
                "No markdown, no prose, no explanations. "
                'Envelope must be exactly {"risks": [...]}.'
            )

        return user_prompt, system_prompt

    # ============================================
    # DOMAIN LOGIC (migrated from risk_extractor.py)
    # ============================================

    def _calculate_risk_score(self, risk: RiskItem) -> int:
        """Calculate numeric risk score (1-12)."""
        impact_score = {
            RiskImpact.LOW: 1,
            RiskImpact.MEDIUM: 2,
            RiskImpact.HIGH: 3,
            RiskImpact.CRITICAL: 4,
        }
        probability_score = {
            RiskProbability.LOW: 1,
            RiskProbability.MEDIUM: 2,
            RiskProbability.HIGH: 3,
        }
        return impact_score[risk.impact] * probability_score[risk.probability]

    def _is_immediate_alert(self, risk: RiskItem) -> bool:
        """Check if risk requires immediate alert."""
        return (
            risk.impact == RiskImpact.CRITICAL
            and risk.probability == RiskProbability.HIGH
        )

    def _extract_items(self, payload: Any) -> list[dict[str, Any]]:
        """Extract risk items from payload."""
        if isinstance(payload, dict):
            raw_items = payload.get("risks")
            if isinstance(raw_items, list):
                return [item for item in raw_items if isinstance(item, dict)]
            if isinstance(raw_items, dict):
                return [raw_items]
            return []
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        return []

    def _coerce_risk(self, item: dict[str, Any]) -> RiskItem | None:
        """Coerce dict to RiskItem with validation."""
        title = self._clean_text(item.get("title"))
        summary = self._clean_text(item.get("summary"))
        description = self._clean_text(item.get("description"))
        if not summary and not title and not description:
            return None

        mitigation = self._clean_text(item.get("mitigation_suggestion"))
        source_quote = self._clean_text(item.get("source_quote"))
        source_text_snippet = self._clean_text(item.get("source_text_snippet"))

        category = self._normalize_category(item.get("category"))
        probability = self._normalize_probability(item.get("probability"))
        impact = self._normalize_impact(item.get("impact"))
        if category is None or probability is None or impact is None:
            return None

        return RiskItem(
            title=title,
            category=category,
            summary=summary,
            description=description,
            probability=probability,
            impact=impact,
            mitigation_suggestion=mitigation,
            source_quote=source_quote,
            source_text_snippet=source_text_snippet,
        )

    def _clean_text(self, value: Any) -> str | None:
        """Clean text value."""
        if not isinstance(value, str):
            return None
        cleaned = value.strip()
        return cleaned or None

    def _normalize_category(self, value: Any) -> RiskCategory | None:
        """Normalize category value."""
        return normalize_category(value if isinstance(value, str) else None)

    def _normalize_probability(self, value: Any) -> RiskProbability | None:
        """Normalize probability value."""
        if not isinstance(value, str):
            return None
        normalized = value.strip().upper()
        for candidate in RiskProbability:
            if candidate.value == normalized:
                return candidate
        return None

    def _normalize_impact(self, value: Any) -> RiskImpact | None:
        """Normalize impact value."""
        if not isinstance(value, str):
            return None
        normalized = value.strip().upper()
        for candidate in RiskImpact:
            if candidate.value == normalized:
                return candidate
        return None

    def _filter_relevant_text(self, text: str) -> str:
        """Filter text to relevant sections for risk extraction.

        Multilingual (ES+EN) keyword include/exclude. Truncation cap is
        configurable via ``RISK_EXTRACTION_MAX_CHARS`` (default 40,000).
        Logs structured events when the include filter falls through
        (no paragraphs matched), so this failure mode is observable.
        """
        paragraphs = self._split_paragraphs(text)
        if not paragraphs:
            return text.strip()

        selected: list[str] = []
        for paragraph in paragraphs:
            lower = paragraph.lower()
            if any(keyword in lower for keyword in _EXCLUDE_KEYWORDS):
                continue
            if any(keyword in lower for keyword in _INCLUDE_KEYWORDS):
                selected.append(paragraph)

        filter_fell_through = not selected
        if filter_fell_through:
            selected = paragraphs
            logger.info(
                "risk_extraction_filter_fellthrough",
                extra={
                    "paragraphs_total": len(paragraphs),
                    "doc_chars": len(text),
                    "reason": "no_include_keyword_match",
                },
            )

        combined = "\n\n".join(selected)
        max_chars = _resolve_max_chars()
        truncated = self._truncate(combined, max_chars=max_chars)
        if len(combined) > len(truncated):
            logger.info(
                "risk_extraction_filter_truncated",
                extra={
                    "original_chars": len(combined),
                    "truncated_chars": len(truncated),
                    "dropped_chars": len(combined) - len(truncated),
                    "max_chars_cap": max_chars,
                    "filter_fell_through": filter_fell_through,
                },
            )
        return truncated

    def _split_paragraphs(self, text: str) -> list[str]:
        """Split text into paragraphs."""
        chunks = re.split(r"\n\s*\n", text)
        return [chunk.strip() for chunk in chunks if chunk.strip()]

    def _truncate(self, text: str, max_chars: int) -> str:
        """Truncate text to max characters."""
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rstrip()

    def _extract_json_from_text(self, text: str) -> Any:
        """Extract JSON from text that may contain markdown or other formatting."""
        # Try to find JSON in code blocks
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find raw JSON
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        return {}

    def _risk_item_to_dict(self, risk: RiskItem) -> dict[str, Any]:
        """Convert RiskItem to dict for state storage."""
        return {
            "category": risk.category.value if risk.category else None,
            "title": risk.title,
            "summary": risk.summary,
            "description": risk.description,
            "probability": risk.probability.value if risk.probability else None,
            "impact": risk.impact.value if risk.impact else None,
            "mitigation_suggestion": risk.mitigation_suggestion,
            "source_quote": risk.source_quote,
            "source_text_snippet": risk.source_text_snippet,
            "risk_score": risk.risk_score,
            "immediate_alert": risk.immediate_alert,
        }
