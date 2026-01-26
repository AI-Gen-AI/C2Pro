from __future__ import annotations

from enum import Enum
import json
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field

from src.ai.ai_service import AIService
from src.modules.stakeholders.models import InterestLevel, PowerLevel, StakeholderQuadrant

STAKEHOLDER_CLASSIFIER_SYSTEM_PROMPT = """
Eres un estratega de producto experto en gestion de proyectos.
Tu trabajo es clasificar stakeholders segun poder e interes usando la matriz de Mendelow.

Instrucciones:
- Usa el rol, la empresa y el tipo de contrato para inferir poder e interes.
- Responde de forma conservadora: si hay ambiguedad, prioriza el riesgo.
- Contesta solo JSON estricto, sin Markdown ni explicaciones.

Preguntas guia:
- Puede esta persona detener la obra o cambiar el alcance? (Power)
- Le afecta directamente un retraso o sobrecosto? (Interest)

Salida esperada:
{
  "stakeholders": [
    {
      "index": 0,
      "power_score": 1-10,
      "interest_score": 1-10,
      "quadrant": "MANAGE_CLOSELY|KEEP_SATISFIED|KEEP_INFORMED|MONITOR"
    }
  ]
}
""".strip()


class MendelowQuadrant(str, Enum):
    MANAGE_CLOSELY = "MANAGE_CLOSELY"
    KEEP_SATISFIED = "KEEP_SATISFIED"
    KEEP_INFORMED = "KEEP_INFORMED"
    MONITOR = "MONITOR"


class StakeholderInput(BaseModel):
    name: str | None = None
    role: str | None = None
    company: str | None = None


class EnrichedStakeholder(BaseModel):
    name: str | None = None
    role: str | None = None
    company: str | None = None
    power_score: int = Field(ge=1, le=10)
    interest_score: int = Field(ge=1, le=10)
    power_level: PowerLevel
    interest_level: InterestLevel
    quadrant: MendelowQuadrant
    quadrant_db: StakeholderQuadrant

    model_config = ConfigDict(use_enum_values=False)


class StakeholderClassifier:
    def __init__(self, tenant_id: str | None = None) -> None:
        self._service = AIService(tenant_id=tenant_id)

    async def classify_batch(
        self,
        stakeholders: list[StakeholderInput],
        contract_type: str | None = None,
    ) -> list[EnrichedStakeholder]:
        if not stakeholders:
            return []

        payload = await self._service.run_extraction(
            STAKEHOLDER_CLASSIFIER_SYSTEM_PROMPT,
            _build_user_payload(stakeholders, contract_type),
        )

        items = _extract_items(payload)
        enriched: list[EnrichedStakeholder] = []
        for idx, stakeholder in enumerate(stakeholders):
            model_item = _find_item(items, idx)
            enriched.append(_merge_result(stakeholder, model_item))
        return enriched


def _build_user_payload(
    stakeholders: Iterable[StakeholderInput],
    contract_type: str | None,
) -> str:
    items = []
    for index, stakeholder in enumerate(stakeholders):
        items.append(
            {
                "index": index,
                "role": stakeholder.role,
                "company": stakeholder.company,
                "contract_type": contract_type,
            }
        )
    return json.dumps({"stakeholders": items}, ensure_ascii=True)


def _extract_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        raw_items = payload.get("stakeholders")
        if isinstance(raw_items, list):
            return [item for item in raw_items if isinstance(item, dict)]
        if isinstance(raw_items, dict):
            return [raw_items]
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _find_item(items: list[dict[str, Any]], index: int) -> dict[str, Any] | None:
    for item in items:
        if item.get("index") == index:
            return item
    return None


def _merge_result(
    stakeholder: StakeholderInput,
    item: dict[str, Any] | None,
) -> EnrichedStakeholder:
    power_score = _normalize_score(item.get("power_score") if item else None, default=5)
    interest_score = _normalize_score(item.get("interest_score") if item else None, default=5)
    quadrant = _normalize_quadrant(item.get("quadrant") if item else None)

    role = stakeholder.role or ""
    applied_override = False
    if _role_has_safety(role):
        power_score = max(power_score, 9)
        applied_override = True
    if _role_is_project_manager(role):
        interest_score = max(interest_score, 9)
        applied_override = True

    if quadrant is None or applied_override:
        quadrant = _derive_quadrant(power_score, interest_score)

    quadrant_db = _map_quadrant_db(quadrant)
    power_level = _score_to_power_level(power_score)
    interest_level = _score_to_interest_level(interest_score)

    return EnrichedStakeholder(
        name=stakeholder.name,
        role=stakeholder.role,
        company=stakeholder.company,
        power_score=power_score,
        interest_score=interest_score,
        power_level=power_level,
        interest_level=interest_level,
        quadrant=quadrant,
        quadrant_db=quadrant_db,
    )


def _normalize_score(value: Any, default: int) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(score, 10))


def _normalize_quadrant(value: Any) -> MendelowQuadrant | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    for candidate in MendelowQuadrant:
        if candidate.value == normalized:
            return candidate
    return None


def _derive_quadrant(power_score: int, interest_score: int) -> MendelowQuadrant:
    high_power = power_score >= 8
    high_interest = interest_score >= 8
    low_power = power_score <= 4
    low_interest = interest_score <= 4

    if high_power and high_interest:
        return MendelowQuadrant.MANAGE_CLOSELY
    if high_power and low_interest:
        return MendelowQuadrant.KEEP_SATISFIED
    if low_power and high_interest:
        return MendelowQuadrant.KEEP_INFORMED
    return MendelowQuadrant.MONITOR


def _map_quadrant_db(quadrant: MendelowQuadrant) -> StakeholderQuadrant:
    mapping = {
        MendelowQuadrant.MANAGE_CLOSELY: StakeholderQuadrant.KEY_PLAYER,
        MendelowQuadrant.KEEP_SATISFIED: StakeholderQuadrant.KEEP_SATISFIED,
        MendelowQuadrant.KEEP_INFORMED: StakeholderQuadrant.KEEP_INFORMED,
        MendelowQuadrant.MONITOR: StakeholderQuadrant.MONITOR,
    }
    return mapping[quadrant]


def _score_to_power_level(score: int) -> PowerLevel:
    if score >= 8:
        return PowerLevel.HIGH
    if score <= 4:
        return PowerLevel.LOW
    return PowerLevel.MEDIUM


def _score_to_interest_level(score: int) -> InterestLevel:
    if score >= 8:
        return InterestLevel.HIGH
    if score <= 4:
        return InterestLevel.LOW
    return InterestLevel.MEDIUM


def _role_has_safety(role: str) -> bool:
    normalized = role.lower()
    return "safety" in normalized or "hse" in normalized


def _role_is_project_manager(role: str) -> bool:
    return "project manager" in role.lower()
