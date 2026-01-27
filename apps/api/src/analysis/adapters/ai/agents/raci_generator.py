from __future__ import annotations

from enum import Enum
import json
from typing import Any, Iterable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.analysis.adapters.ai.agents.base_agent import BaseAgent
from src.stakeholders.domain.models import RACIRole

RACI_SYSTEM_PROMPT = """
Eres un PMP Certified Project Manager y experto en razonamiento contractual.
Genera asignaciones RACI basadas en items de WBS, stakeholders y clausulas relevantes.

Reglas:
- Busca verbos clave en las clausulas asociadas a cada tarea.
- "El Contratista ejecutara" -> Contratista = R.
- "Sujeto a la aprobacion del Cliente" -> Cliente = A.
- "Previa revision de Ingenieria" -> Ingenieria = C.
- "Se notificara al Supervisor" -> Supervisor = I.

Formato de salida:
Devuelve SOLO JSON estricto con la clave "assignments".
Si no puedes asignar, devuelve {"assignments": []}.

Esquema:
{
  "assignments": [
    {
      "wbs_item_id": "uuid",
      "stakeholder_id": "uuid",
      "role": "R|A|C|I",
      "evidence_text": "Fragmento textual que justifica la asignacion"
    }
  ]
}
""".strip()


class WBSItemInput(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    clause_text: str | None = None


class StakeholderInput(BaseModel):
    id: UUID
    name: str | None = None
    role: str | None = None
    company: str | None = None
    stakeholder_type: str | None = None


class RaciAssignment(BaseModel):
    wbs_item_id: UUID
    stakeholder_id: UUID
    role: RACIRole
    evidence_text: str | None = None

    model_config = ConfigDict(use_enum_values=False)


class RaciGenerationResult(BaseModel):
    assignments: list[RaciAssignment]
    warnings: list[str] = Field(default_factory=list)


class RaciGeneratorAgent(BaseAgent):
    async def generate_assignments(
        self,
        *,
        wbs_items: list[WBSItemInput],
        stakeholders: list[StakeholderInput],
    ) -> RaciGenerationResult:
        if not wbs_items or not stakeholders:
            return RaciGenerationResult(assignments=[], warnings=[])

        payload = await self._run_with_retry(
            RACI_SYSTEM_PROMPT,
            _build_user_payload(wbs_items=wbs_items, stakeholders=stakeholders),
        )
        assignments = _parse_assignments(payload)

        assignments = _ensure_accountable(assignments, wbs_items, stakeholders)
        warnings = check_raci_rules(assignments, wbs_items)

        return RaciGenerationResult(assignments=assignments, warnings=warnings)


def _build_user_payload(
    *,
    wbs_items: Iterable[WBSItemInput],
    stakeholders: Iterable[StakeholderInput],
) -> str:
    return json.dumps(
        {
            "wbs_items": [
                {
                    "id": str(item.id),
                    "name": item.name,
                    "description": item.description,
                    "clause_text": item.clause_text,
                }
                for item in wbs_items
            ],
            "stakeholders": [
                {
                    "id": str(stakeholder.id),
                    "name": stakeholder.name,
                    "role": stakeholder.role,
                    "company": stakeholder.company,
                    "type": stakeholder.stakeholder_type,
                }
                for stakeholder in stakeholders
            ],
        },
        ensure_ascii=True,
    )


def _parse_assignments(payload: Any) -> list[RaciAssignment]:
    items: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        raw_items = payload.get("assignments")
        if isinstance(raw_items, list):
            items = [item for item in raw_items if isinstance(item, dict)]
        elif isinstance(raw_items, dict):
            items = [raw_items]
    elif isinstance(payload, list):
        items = [item for item in payload if isinstance(item, dict)]

    assignments: list[RaciAssignment] = []
    for item in items:
        assignment = _coerce_assignment(item)
        if assignment:
            assignments.append(assignment)
    return assignments


def _coerce_assignment(item: dict[str, Any]) -> RaciAssignment | None:
    try:
        wbs_id = UUID(str(item.get("wbs_item_id")))
        stakeholder_id = UUID(str(item.get("stakeholder_id")))
    except Exception:
        return None

    role_value = str(item.get("role", "")).strip().upper()
    role = None
    for candidate in RACIRole:
        if candidate.value == role_value:
            role = candidate
            break
    if role is None:
        return None

    evidence = item.get("evidence_text")
    if isinstance(evidence, str):
        evidence = evidence.strip() or None
    else:
        evidence = None

    return RaciAssignment(
        wbs_item_id=wbs_id,
        stakeholder_id=stakeholder_id,
        role=role,
        evidence_text=evidence,
    )


def _ensure_accountable(
    assignments: list[RaciAssignment],
    wbs_items: Iterable[WBSItemInput],
    stakeholders: Iterable[StakeholderInput],
) -> list[RaciAssignment]:
    existing = list(assignments)
    by_wbs = {item.id: [] for item in wbs_items}
    for assignment in existing:
        by_wbs.setdefault(assignment.wbs_item_id, []).append(assignment)

    fallback = _select_accountable_fallback(stakeholders)
    if fallback is None:
        return existing

    for wbs_id, row in by_wbs.items():
        if any(item.role == RACIRole.ACCOUNTABLE for item in row):
            continue
        existing.append(
            RaciAssignment(
                wbs_item_id=wbs_id,
                stakeholder_id=fallback.id,
                role=RACIRole.ACCOUNTABLE,
                evidence_text="Asignado por regla de fallback (Accountable).",
            )
        )
    return existing


def _select_accountable_fallback(
    stakeholders: Iterable[StakeholderInput],
) -> StakeholderInput | None:
    for stakeholder in stakeholders:
        role = (stakeholder.role or "").lower()
        if "cliente" in role or "owner" in role or "client" in role:
            return stakeholder
    for stakeholder in stakeholders:
        role = (stakeholder.role or "").lower()
        if "project manager" in role:
            return stakeholder
    return next(iter(stakeholders), None)


def check_raci_rules(
    assignments: list[RaciAssignment],
    wbs_items: Iterable[WBSItemInput],
) -> list[str]:
    warnings: list[str] = []
    by_wbs: dict[UUID, list[RaciAssignment]] = {item.id: [] for item in wbs_items}
    for assignment in assignments:
        by_wbs.setdefault(assignment.wbs_item_id, []).append(assignment)

    for wbs in wbs_items:
        row = by_wbs.get(wbs.id, [])
        accountable = [item for item in row if item.role == RACIRole.ACCOUNTABLE]
        responsible = [item for item in row if item.role == RACIRole.RESPONSIBLE]
        if not accountable:
            warnings.append(f"WBS {wbs.id} sin Accountable.")
        elif len(accountable) > 1:
            warnings.append(f"WBS {wbs.id} con multiples Accountable.")
        if not responsible:
            warnings.append(f"WBS {wbs.id} sin Responsible.")
    return warnings
