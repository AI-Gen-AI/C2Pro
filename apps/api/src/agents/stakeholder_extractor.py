from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Any

from .base_agent import BaseAgent

STAKEHOLDER_SYSTEM_PROMPT = """
Eres un extractor de partes intervinientes en contratos de obra.
Tu salida DEBE ser JSON estricto y valido, sin Markdown ni explicaciones.

Objetivo:
- Identifica a la entidad "Cliente" (dueno de la obra) y "Contratista" (ejecutor).
- Extrae representantes legales y sus cargos si aparecen.
- Ignora notarios, registradores, o figuras irrelevantes para la ejecucion.

Reglas:
- Devuelve SOLO un objeto JSON con la clave "stakeholders".
- Si no hay datos, devuelve: {"stakeholders": []}
- Campos opcionales que no existan deben ser null (no uses texto vacio).
- Enum "type": CLIENT, CONTRACTOR, SUBCONTRACTOR, SUPERVISION.

Esquema estricto:
{
  "stakeholders": [
    {
      "name": "Nombre completo",
      "role": "Cargo o rol",
      "company": "Empresa u organizacion",
      "type": "CLIENT|CONTRACTOR|SUBCONTRACTOR|SUPERVISION",
      "contact_email": "email@dominio.com"
    }
  ]
}
""".strip()


class StakeholderType(str, Enum):
    CLIENT = "CLIENT"
    CONTRACTOR = "CONTRACTOR"
    SUBCONTRACTOR = "SUBCONTRACTOR"
    SUPERVISION = "SUPERVISION"


@dataclass
class Stakeholder:
    name: str
    role: str | None
    company: str | None
    type: StakeholderType
    contact_email: str | None


class StakeholderExtractorAgent(BaseAgent):
    """
    Extracts stakeholder entities from contract text.
    """

    async def extract(self, text_chunk: str) -> list[Stakeholder]:
        if not text_chunk or not text_chunk.strip():
            return []

        selected_text = _select_relevant_text(text_chunk)
        payload = await self._run_with_retry(STAKEHOLDER_SYSTEM_PROMPT, selected_text)
        items = _extract_items(payload)

        stakeholders: list[Stakeholder] = []
        for item in items:
            stakeholder = _coerce_stakeholder(item)
            if stakeholder:
                stakeholders.append(stakeholder)
        return stakeholders


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


def _coerce_stakeholder(item: dict[str, Any]) -> Stakeholder | None:
    name = _clean_text(item.get("name"))
    if not name:
        return None

    role = _clean_text(item.get("role"))
    company = _clean_text(item.get("company"))
    email = _clean_email(item.get("contact_email"))
    type_value = _normalize_type(item.get("type"), role, company, name)
    if type_value is None:
        return None

    return Stakeholder(
        name=name,
        role=role,
        company=company,
        type=type_value,
        contact_email=email,
    )


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _clean_email(value: Any) -> str | None:
    email = _clean_text(value)
    if not email:
        return None
    if "@" not in email:
        return None
    return email


def _normalize_type(
    value: Any,
    role: str | None,
    company: str | None,
    name: str | None,
) -> StakeholderType | None:
    tokens = " ".join(part for part in (value, role, company, name) if isinstance(part, str)).lower()
    if "cliente" in tokens or "dueno" in tokens or "propietario" in tokens or "mandante" in tokens:
        return StakeholderType.CLIENT
    if "contratista" in tokens or "ejecutor" in tokens:
        return StakeholderType.CONTRACTOR
    if "subcontratista" in tokens or "subcontrat" in tokens:
        return StakeholderType.SUBCONTRACTOR
    if "supervision" in tokens or "interventor" in tokens or "inspector" in tokens:
        return StakeholderType.SUPERVISION

    if isinstance(value, str):
        normalized = value.strip().upper()
        for candidate in StakeholderType:
            if candidate.value == normalized:
                return candidate
    return None


def _split_pages(text: str) -> list[str]:
    if "\f" in text:
        pages = text.split("\f")
        return [page.strip() for page in pages if page.strip()]

    page_marker = r"(?:\r?\n)(?:-+\s*)?(?:page|pagina|pag\.?)\s+\d+(?:\s*/\s*\d+|\s+de\s+\d+)?(?:\s*-+)?(?:\r?\n)"
    parts = re.split(page_marker, text, flags=re.IGNORECASE)
    return [part.strip() for part in parts if part.strip()]


def _select_relevant_text(text: str, first_pages: int = 10, last_pages: int = 5) -> str:
    pages = _split_pages(text)
    if not pages:
        return text.strip()
    if len(pages) <= first_pages + last_pages:
        return "\n\n".join(pages)

    head = "\n\n".join(pages[:first_pages])
    tail = "\n\n".join(pages[-last_pages:])
    return f"[INICIO]\n{head}\n\n[FIN]\n{tail}"
