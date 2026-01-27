from __future__ import annotations

from typing import Any

from src.analysis.adapters.ai.anthropic_client import AIService

RISK_SYSTEM_PROMPT = """
Eres un analista de riesgos de proyectos de construccion.
Extrae los riesgos contractuales y operativos del texto.
Devuelve SOLO un JSON array con objetos:
[{ "title": "...", "description": "...", "severity": "low|medium|high|critical", "confidence": 0-1 }]
""".strip()


class RiskExtractionAgent:
    def __init__(self, tenant_id: str | None = None) -> None:
        self._service = AIService(tenant_id=tenant_id)

    async def extract(self, document_text: str) -> list[dict[str, Any]]:
        payload = await self._service.run_extraction(RISK_SYSTEM_PROMPT, document_text)
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            return [payload]
        return []
