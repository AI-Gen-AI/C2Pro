from __future__ import annotations

from typing import Any

from src.ai.ai_service import AIService

WBS_SYSTEM_PROMPT = """
Eres un planificador de proyectos.
Genera una lista WBS a partir del texto tecnico.
Devuelve SOLO un JSON array con objetos:
[{ "code": "...", "name": "...", "description": "...", "item_type": "deliverable|work_package|activity", "confidence": 0-1 }]
""".strip()


class WBSExtractionAgent:
    def __init__(self, tenant_id: str | None = None) -> None:
        self._service = AIService(tenant_id=tenant_id)

    async def extract(self, document_text: str) -> list[dict[str, Any]]:
        payload = await self._service.run_extraction(WBS_SYSTEM_PROMPT, document_text)
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            return [payload]
        return []
