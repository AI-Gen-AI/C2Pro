"""
analysis/adapters/ai/tools/risk_extraction_tool.py

Extracts contractual and project risks from narrative sections.
"""
from __future__ import annotations

import json
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
from src.core.ai.anthropic_wrapper import AIResponse
from src.core.ai.model_router import AITaskType
from src.core.ai.tools import BaseTool, ToolResult, register_tool

if TYPE_CHECKING:
    from src.analysis.adapters.graph.schema import ProjectState


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

    async def _execute_impl(
        self,
        input_data: RiskExtractionInput,
        tenant_id: UUID | None,
        ai_response: AIResponse,
    ) -> list[RiskItem]:
        """Parse AI response and apply domain logic."""

        # Apply filtering if requested
        if input_data.filter_relevant:
            if input_data.filter_relevant:
    input_data.document_text = self._filter_relevant_text(input_data.document_text)
        else:
            filtered_text = input_data.document_text

        # Parse JSON response
        try:
            payload = json.loads(ai_response.content)
        except json.JSONDecodeError:
            # Fallback: try to extract JSON from text
            payload = self._extract_json_from_text(ai_response.content)

        # Extract risk items
        items = self._extract_items(payload)

        # Coerce to RiskItem models with validation
        risks: list[RiskItem] = []
        for item in items:
            risk = self._coerce_risk(item)
            if risk:
                # Apply domain logic
                risk.risk_score = self._calculate_risk_score(risk)
                risk.immediate_alert = self._is_immediate_alert(risk)
                risks.append(risk)

        # Sort by risk score
        risks.sort(key=lambda r: r.risk_score, reverse=True)

        # Apply max_risks limit
        if len(risks) > input_data.max_risks:
            risks = risks[: input_data.max_risks]

        return risks

    def extract_input_from_state(self, state: ProjectState) -> RiskExtractionInput:
        """Extract input from LangGraph state."""
        # Apply document augmentation from state
        doc_text = state["document_text"]

        if state.get("critique_notes"):
            doc_text = f"{doc_text}\n\nCRITIQUE: {state['critique_notes']}"

        if state.get("human_feedback"):
            doc_text = f"{doc_text}\n\nFEEDBACK: {state['human_feedback']}"

        return RiskExtractionInput(
            document_text=doc_text,
            max_risks=20,
            filter_relevant=True,
        )

    def inject_output_into_state(
        self,
        state: ProjectState,
        result: ToolResult[list[RiskItem]],
    ) -> ProjectState:
        """Inject output into LangGraph state."""
        # Convert RiskItems to dicts for state storage
        state["extracted_risks"] = [
            self._risk_item_to_dict(risk) for risk in result.data
        ]

        # Update confidence score based on result quality
        if result.confidence_score:
            if result.data:
    confidences = [item.confidence for item in result.data]
    state["confidence_score"] = sum(confidences) / len(confidences) if confidences else 0.9
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
        """Build prompt for risk extraction."""
        system_prompt = """
Eres un analista senior de riesgos de proyectos de infraestructura.
Extrae riesgos contractuales y del proyecto de las secciones narrativas del contrato.

Identifica:
- Riesgos LEGALES: obligaciones, penalizaciones, responsabilidades
- Riesgos FINANCIEROS: garantías, multas, pagos
- Riesgos de CRONOGRAMA: plazos críticos, dependencias, retrasos
- Riesgos TÉCNICOS: especificaciones, geotecnia, calidad
- Riesgos HSE: seguridad, medio ambiente, permisos
- Riesgos de CALIDAD: ensayos, pruebas, normativas

Para cada riesgo devuelve:
{
  "category": "LEGAL|FINANCIAL|SCHEDULE|TECHNICAL|HSE|QUALITY",
  "title": "Título breve del riesgo",
  "summary": "Resumen corto",
  "description": "Descripción detallada",
  "probability": "LOW|MEDIUM|HIGH",
  "impact": "LOW|MEDIUM|HIGH|CRITICAL",
  "mitigation_suggestion": "Sugerencia de mitigación",
  "source_quote": "Cita textual del documento",
  "source_text_snippet": "Fragmento del texto fuente"
}

IMPORTANTE: Devuelve SOLO un JSON con formato:
{"risks": [... array de objetos de riesgo ...]}
""".strip()

        user_prompt = f"DOCUMENTO:\n\n{input_data.document_text}"

        if is_retry:
            user_prompt = (
                f"{user_prompt}\n\n"
                "IMPORTANTE: Responde SOLO con JSON válido. "
                "No uses Markdown, no agregues explicaciones."
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
        if not isinstance(value, str):
            return None
        normalized = value.strip().upper()
        for candidate in RiskCategory:
            if candidate.value == normalized:
                return candidate
        return None

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
        """Filter text to relevant sections for risk extraction."""
        paragraphs = self._split_paragraphs(text)
        if not paragraphs:
            return text.strip()

        include_keywords = (
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
        exclude_keywords = (
            "tabla de precios",
            "precio unitario",
            "medicion y pago",
            "presupuesto",
            "subtotal",
            "total",
            "bill of materials",
            "bom",
        )

        selected = []
        for paragraph in paragraphs:
            lower = paragraph.lower()
            if any(keyword in lower for keyword in exclude_keywords):
                continue
            if any(keyword in lower for keyword in include_keywords):
                selected.append(paragraph)

        if not selected:
            selected = paragraphs

        combined = "\n\n".join(selected)
        return self._truncate(combined, max_chars=15000)

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
