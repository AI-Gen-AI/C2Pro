from __future__ import annotations

from enum import Enum
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .base_agent import BaseAgent
from .risk_prompts import RISK_SYSTEM_PROMPT


class RiskCategory(str, Enum):
    LEGAL = "LEGAL"
    FINANCIAL = "FINANCIAL"
    SCHEDULE = "SCHEDULE"
    TECHNICAL = "TECHNICAL"
    HSE = "HSE"
    QUALITY = "QUALITY"


class RiskProbability(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RiskImpact(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskItem(BaseModel):
    title: str | None = Field(None, description="Brief risk title")
    summary: str | None = Field(None, description="Short risk summary")
    description: str | None = None
    category: RiskCategory
    probability: RiskProbability
    impact: RiskImpact
    mitigation_suggestion: str | None = None
    source_quote: str | None = None
    source_text_snippet: str | None = None
    risk_score: int = 0
    immediate_alert: bool = False

    model_config = ConfigDict(use_enum_values=False)


class RiskExtractorAgent(BaseAgent):
    """
    Extracts contractual and project risks from narrative contract sections.
    """

    async def extract(self, text_chunk: str) -> list[RiskItem]:
        if not text_chunk or not text_chunk.strip():
            return []

        filtered_text = _filter_relevant_text(text_chunk)
        payload = await self._run_with_retry(RISK_SYSTEM_PROMPT, filtered_text)
        items = _extract_items(payload)

        risks: list[RiskItem] = []
        for item in items:
            risk = _coerce_risk(item)
            if risk:
                risk.risk_score = _risk_score(risk)
                risk.immediate_alert = _is_immediate_alert(risk)
                risks.append(risk)
        risks.sort(key=lambda r: r.risk_score, reverse=True)
        return risks


def _extract_items(payload: Any) -> list[dict[str, Any]]:
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


def _coerce_risk(item: dict[str, Any]) -> RiskItem | None:
    title = _clean_text(item.get("title"))
    summary = _clean_text(item.get("summary"))
    description = _clean_text(item.get("description"))
    if not summary and not title and not description:
        return None

    mitigation = _clean_text(item.get("mitigation_suggestion"))
    source_quote = _clean_text(item.get("source_quote"))
    source_text_snippet = _clean_text(item.get("source_text_snippet"))

    category = _normalize_category(item.get("category"))
    probability = _normalize_probability(item.get("probability"))
    impact = _normalize_impact(item.get("impact"))
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


def _is_immediate_alert(risk: RiskItem) -> bool:
    return risk.impact == RiskImpact.CRITICAL and risk.probability == RiskProbability.HIGH


def _risk_score(risk: RiskItem) -> int:
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


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_category(value: Any) -> RiskCategory | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    for candidate in RiskCategory:
        if candidate.value == normalized:
            return candidate
    return None


def _normalize_probability(value: Any) -> RiskProbability | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    for candidate in RiskProbability:
        if candidate.value == normalized:
            return candidate
    return None


def _normalize_impact(value: Any) -> RiskImpact | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    for candidate in RiskImpact:
        if candidate.value == normalized:
            return candidate
    return None


def _filter_relevant_text(text: str) -> str:
    paragraphs = _split_paragraphs(text)
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
    return _truncate(combined, max_chars=15000)


def _split_paragraphs(text: str) -> list[str]:
    chunks = re.split(r"\n\s*\n", text)
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip()
