"""
analysis/adapters/ai/tools/wbs_extraction_tool.py

Extracts Work Breakdown Structure (WBS) items from technical documents.

Test Suite ID: TS-QA-SWAGGER-ANALYSIS-001
"""
from __future__ import annotations

import json
import re
from datetime import date
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.analysis.domain.ai_source_text import llm_document_text
from src.analysis.domain.critique_evaluation import CritiqueEvaluationService
from src.core.ai.anthropic_wrapper import AIResponse
from src.core.ai.model_router import AITaskType
from src.core.ai.tools import BaseTool, ToolResult, register_tool
from src.projects.domain.wbs_hierarchy import WBSHierarchy

if TYPE_CHECKING:
    from src.analysis.adapters.graph.schema import ProjectState


class WBSExtractionInput(BaseModel):
    """Input for WBS extraction."""

    document_text: str = Field(..., description="Technical document text to analyze")
    max_items: int = Field(50, ge=1, le=100, description="Maximum WBS items to extract")


class WBSItemOutput(BaseModel):
    """Output model for a single WBS item."""

    code: str = Field(..., description="WBS code (e.g., 1.2.3)")
    name: str = Field(..., description="Item name")
    description: str | None = Field(None, description="Item description")
    source_quote: str | None = Field(
        None, description="Verbatim contiguous passage from the technical source that supports this WBS element"
    )
    level: int | None = Field(
        default=None,
        ge=0,
        description="Source-supplied WBS depth; derived from a valid numeric code only when absent",
    )
    parent_code: str | None = Field(
        default=None,
        description="Direct numeric parent emitted in this result; not semantic source validation",
    )
    item_type: str = Field(
        ..., description="Item type: deliverable, work_package, or activity"
    )
    confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Assessed confidence when available"
    )
    budget_allocated: float | None = Field(
        None, description="Allocated budget if mentioned"
    )
    start_date: date | None = Field(None, description="Planned start date if mentioned")
    end_date: date | None = Field(None, description="Planned end date if mentioned")
    predecessor_id: str | None = Field(None, description="Explicit predecessor identifier if mentioned")
    status: str | None = Field(None, description="Schedule status if mentioned")

    @field_validator("item_type")
    @classmethod
    def validate_item_type(cls, v: str) -> str:
        """Validate item_type is one of the allowed values."""
        allowed = ["deliverable", "work_package", "activity"]
        if v.lower() not in allowed:
            raise ValueError(f"item_type must be one of {allowed}, got {v}")
        return v.lower()


@register_tool("wbs_extraction", version="1.0")
class WBSExtractionTool(BaseTool[WBSExtractionInput, list[WBSItemOutput]]):
    """
    Extracts Work Breakdown Structure (WBS) items from technical documents.

    Capabilities:
    - Identifies deliverables, work packages, and activities
    - Assigns WBS codes hierarchically
    - Extracts descriptions and budget information if available
    - Returns structured WBS items with confidence scores

    Input: Technical document text
    Output: List of WBSItemOutput with code, name, description, type
    """

    name = "wbs_extraction"
    version = "1.0"
    description = "Extracts Work Breakdown Structure items from technical documents"
    task_type = AITaskType.COMPLEX_EXTRACTION
    prompt_template_name = None  # Using inline prompt

    async def _execute_impl(
        self,
        input_data: WBSExtractionInput,
        tenant_id: UUID | None,
        ai_response: AIResponse,
    ) -> list[WBSItemOutput]:
        """Parse AI response and apply domain logic."""
        _ = tenant_id

        # Parse JSON response
        try:
            payload = json.loads(ai_response.content)
        except json.JSONDecodeError:
            # Fallback: try to extract JSON from text
            payload = self._extract_json_from_text(ai_response.content)

        # Extract items
        items = self._extract_items(payload)

        # Coerce to WBSItemOutput models with validation
        wbs_items: list[WBSItemOutput] = []
        for item in items:
            try:
                wbs_item = WBSItemOutput(**item)
                wbs_items.append(wbs_item)
            except Exception:
                # Skip invalid items
                continue

        # Apply max_items limit
        if len(wbs_items) > input_data.max_items:
            wbs_items = wbs_items[: input_data.max_items]

        return self._resolve_hierarchy(wbs_items)

    def extract_input_from_state(self, state: ProjectState) -> WBSExtractionInput:
        """Extract input from LangGraph state."""
        # Apply document augmentation from state
        doc_text = llm_document_text(state)

        if state.get("critique_notes"):
            doc_text = f"{doc_text}\n\nCRITIQUE: {state['critique_notes']}"

        if state.get("human_feedback"):
            doc_text = f"{doc_text}\n\nFEEDBACK: {state['human_feedback']}"

        return WBSExtractionInput(
            document_text=doc_text,
            max_items=50,
        )

    def inject_output_into_state(
        self,
        state: ProjectState,
        result: ToolResult[list[WBSItemOutput]],
    ) -> ProjectState:
        """Inject output into LangGraph state."""
        # Convert WBSItemOutput to dicts for state storage
        resolved_items = self._resolve_hierarchy(result.data)
        state["extracted_wbs"] = [item.model_dump(mode="json") for item in resolved_items]

        # Tool-level quality metadata is not individual WBS confidence.
        # A synthetic 0.9 default would falsely certify every unassessed item.
        state["confidence_score"] = CritiqueEvaluationService().calculate_confidence(
            state["extracted_wbs"]
        )

        return state

    def _build_default_prompt(
        self, input_data: WBSExtractionInput, is_retry: bool
    ) -> tuple[str, str | None]:
        """Build prompt for WBS extraction."""
        system_prompt = """
Eres un planificador de proyectos experto en Work Breakdown Structure (WBS).
Genera una lista WBS a partir del texto técnico proporcionado.

Para cada elemento WBS identifica:
- code: Código jerárquico (ej: 1.2.3)
- name: Nombre del elemento
- description: Descripción basada exclusivamente en la fuente; evita desglosar actividades implícitas como hechos
- source_quote: Fragmento CONTIGUO y LITERAL del DOCUMENTO TÉCNICO que justifica este elemento. Copia el texto exacto, no una paráfrasis. Si no existe respaldo textual, OMITE el elemento.
- level: Nivel WBS de la fuente si se declara; si no, null
- parent_code: Código del padre directo solo si dicho padre también aparece en la salida
- item_type: Tipo de elemento (deliverable | work_package | activity)
  * deliverable: Entregable final del proyecto
  * work_package: Paquete de trabajo que agrupa actividades
  * activity: Actividad específica a realizar
- confidence: Nivel de confianza (0.0 a 1.0)
- budget_allocated: Presupuesto asignado si se menciona (opcional)
- start_date: Fecha de inicio planificada ISO-8601 si se menciona (opcional)
- end_date: Fecha de fin planificada ISO-8601 si se menciona (opcional)
- predecessor_id: Identificador de predecesora explicita si se menciona (opcional)
- status: Estado de cronograma si se menciona (opcional)

IMPORTANTE: Devuelve SOLO un JSON con el formato:
[
  {
    "code": "1.1",
    "name": "Diseño estructural",
    "description": "Diseño completo de la estructura del edificio",
    "source_quote": "Texto exacto del documento que describe este trabajo",
    "level": 1,
    "parent_code": "1",
    "item_type": "work_package",
    "confidence": 0.95,
    "budget_allocated": 50000.0,
    "start_date": "2026-01-01",
    "end_date": "2026-04-15",
    "predecessor_id": null,
    "status": "on_track"
  },
  ...
]

Reglas:
- Los códigos deben ser jerárquicos (1, 1.1, 1.1.1, etc.)
- No inventes nodos padre ni agrupaciones. Si falta el padre directo en el texto/salida, usa parent_code: null.
- parent_code no valida una relación semántica: el sistema solo conservará el padre directo
  derivable del código numérico y presente en la salida. No presentes una agrupación inferida como fuente.
- Cada elemento debe incluir source_quote literal, presente en el texto suministrado; sin fuente inequívoca NO generes el elemento.
- No conviertas una explicación o consecuencia genérica en una actividad WBS supuestamente explícita.
- No inventes detalles técnicos no respaldados por el documento (incluidos as-built o certificados).
  Conserva una fecha FAT explícita exactamente como aparece; no la sustituyas por una fecha inferida.
- Los detalles técnicos no corroborados son provisionales y requieren revisión humana. Un JSON
  generado no constituye validación semántica ni aprobación de esos detalles.
- deliverables son los productos finales
- work_packages agrupan múltiples actividades
- activities son tareas específicas
""".strip()

        user_prompt = f"DOCUMENTO TÉCNICO:\n\n{input_data.document_text}"

        if is_retry:
            user_prompt = (
                f"{user_prompt}\n\n"
                "IMPORTANTE: Responde SOLO con JSON válido. "
                "No uses Markdown, no agregues explicaciones. "
                "Devuelve un array JSON directamente."
            )

        return user_prompt, system_prompt

    # ============================================
    # HELPER METHODS
    # ============================================

    def _extract_items(self, payload: Any) -> list[dict[str, Any]]:
        """Extract WBS items from payload."""
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            # Check if it's wrapped in a "wbs_items" or "items" key
            if "wbs_items" in payload:
                items = payload["wbs_items"]
                if isinstance(items, list):
                    return [item for item in items if isinstance(item, dict)]
            if "items" in payload:
                items = payload["items"]
                if isinstance(items, list):
                    return [item for item in items if isinstance(item, dict)]
            # Otherwise treat the dict itself as a single item
            return [payload]
        return []

    @classmethod
    def _resolve_hierarchy(cls, items: list[WBSItemOutput]) -> list[WBSItemOutput]:
        """Derive only direct numeric parents that are present in this result."""
        valid_codes = {item.code for item in items if WBSHierarchy.validate_code(item.code)}
        resolved: list[WBSItemOutput] = []
        for item in items:
            code_is_valid = item.code in valid_codes
            candidate = WBSHierarchy.parent_code(item.code) if code_is_valid else None

            # A supplied parent cannot override the canonical direct-prefix
            # relationship. This rejects cross-links (for example 1.2.1 -> 1.1)
            # and never synthesizes a missing parent node.
            parent_code = candidate if candidate in valid_codes else None

            level = item.level if item.level is not None else (
                item.code.count(".") if code_is_valid else None
            )
            resolved.append(item.model_copy(update={"parent_code": parent_code, "level": level}))
        return resolved

    def _extract_json_from_text(self, text: str) -> Any:
        """Extract JSON from text that may contain markdown or other formatting."""
        # Try to find JSON in code blocks
        json_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find JSON object in code blocks
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find raw JSON array
        json_match = re.search(r"\[.*\]", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        # Try to find raw JSON object
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        return []
