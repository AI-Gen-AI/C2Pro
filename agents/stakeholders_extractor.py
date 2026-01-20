"""
Stakeholder Extraction Agent.

Extracts and normalizes stakeholders from contract text with role taxonomy,
relationship inference, and anonymization-aware behavior.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, TypeAdapter



class StakeholderRole(str, Enum):
    CLIENT = "CLIENT"
    MAIN_CONTRACTOR = "MAIN_CONTRACTOR"
    SUBCONTRACTOR = "SUBCONTRACTOR"
    PROJECT_MANAGER = "PROJECT_MANAGER"
    HEALTH_SAFETY = "HEALTH_SAFETY"
    ADMIN = "ADMIN"


class ContactInfo(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class StakeholderExtraction(BaseModel):
    name: str = Field(..., min_length=1)
    company_name: Optional[str] = None
    role: StakeholderRole
    contact_info: ContactInfo = Field(default_factory=ContactInfo)
    is_legal_entity: bool
    reports_to: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


StakeholderExtractionList = TypeAdapter(list[StakeholderExtraction])


SYSTEM_PROMPT = """
Eres un Contract Administrator experto en contratos de construccion.
Tu tarea es extraer stakeholders (personas y entidades) del texto contractual
y normalizarlos con la taxonomía de roles.

Busca especialmente las secciones:
- "Reunidos"
- "Intervienen"
- "Clausula de Notificaciones"
- "Representantes del Proyecto"

Roles permitidos (enum):
- CLIENT (Promotor/Dueño)
- MAIN_CONTRACTOR (Contratista Principal)
- SUBCONTRACTOR (Subcontrata)
- PROJECT_MANAGER (Direccion Facultativa)
- HEALTH_SAFETY (Coordinador de Seguridad)
- ADMIN (Administrativo)

Reglas críticas:
- Unifica menciones equivalentes (p.ej. "El Contratista", "Acme S.L.", "Parte Ejecutora").
- No inventes nombres. Si el texto esta anonimizado, conserva el placeholder literal.
- Inferir jerarquia: si dice "Juan Perez, actuando en nombre de Constructora X",
  entonces reports_to de Juan Pérez es "Constructora X".
- Si no hay contacto, usa null en email/phone.

Salida requerida: SOLO un JSON array con objetos del schema:
[
  {
    "name": "...",
    "company_name": "...",
    "role": "CLIENT|MAIN_CONTRACTOR|SUBCONTRACTOR|PROJECT_MANAGER|HEALTH_SAFETY|ADMIN",
    "contact_info": {"email": "...", "phone": "..."},
    "is_legal_entity": true/false,
    "reports_to": "..."
  }
]
No incluyas texto adicional fuera del JSON.
""".strip()


class StakeholderExtractionAgent:
    """
    AI agent wrapper for extracting stakeholders from contract text.
    """

    def __init__(self) -> None:
        from src.modules.ai.anthropic_wrapper import get_anthropic_wrapper

        self._wrapper = get_anthropic_wrapper()

    async def extract(self, contract_text: str, tenant_id: UUID | None = None) -> list[StakeholderExtraction]:
        from src.modules.ai.anthropic_wrapper import AIRequest
        from src.modules.ai.model_router import AITaskType

        if not contract_text or not contract_text.strip():
            return []

        request = AIRequest(
            prompt=contract_text,
            system_prompt=SYSTEM_PROMPT,
            task_type=AITaskType.STAKEHOLDER_CLASSIFICATION,
            tenant_id=tenant_id,
            use_cache=True,
        )

        response = await self._wrapper.generate(request)
        payload = _extract_json_array(response.content)
        raw_items = json.loads(payload)

        for item in raw_items:
            if "contact_info" not in item or item["contact_info"] is None:
                item["contact_info"] = {}

        return StakeholderExtractionList.validate_python(raw_items)


def _extract_json_array(raw: str) -> str:
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError("LLM response did not include a JSON array.")
    return raw[start : end + 1]
