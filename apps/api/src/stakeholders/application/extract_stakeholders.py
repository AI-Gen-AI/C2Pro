"""
Use Case for Stakeholder Extraction from contract text.
"""

import json
import re
from typing import List, Any, Optional
from uuid import UUID, uuid4

# Import domain models
from src.stakeholders.domain.models import Stakeholder, StakeholderRole, ContactInfo

# Temporary import for AI dependencies. This will be refactored into an adapter later.
from src.modules.ai.anthropic_wrapper import get_anthropic_wrapper
from src.modules.ai.model_router import AITaskType

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


class ExtractStakeholdersUseCase:
    """
    Use Case for extracting stakeholders from contract text using an AI provider.
    """

    def __init__(self, ai_provider: Any) -> None:
        self._ai_provider = ai_provider

    async def execute(self, contract_text: str, tenant_id: Optional[UUID] = None) -> List[Stakeholder]:
        if not contract_text or not contract_text.strip():
            return []

        from src.modules.ai.anthropic_wrapper import AIRequest

        request = AIRequest(
            prompt=contract_text,
            system_prompt=SYSTEM_PROMPT,
            task_type=AITaskType.STAKEHOLDER_CLASSIFICATION,
            tenant_id=tenant_id,
            use_cache=True,
        )

        response = await self._ai_provider.generate(request)
        payload = _extract_json_array(response.content)
        raw_items = json.loads(payload)

        for item in raw_items:
            if "contact_info" not in item or item["contact_info"] is None:
                item["contact_info"] = {}
            if "id" not in item:
                item["id"] = str(uuid4())

        return [Stakeholder.model_validate(item) for item in raw_items]


def _extract_json_array(raw: str) -> str:
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"LLM response did not include a valid JSON array. Raw response: {raw[:200]}...")
    return raw[start : end + 1]
