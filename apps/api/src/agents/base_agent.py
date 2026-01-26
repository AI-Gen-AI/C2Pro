from __future__ import annotations

from typing import Any

import structlog

from src.ai.ai_service import AIService
from src.core.exceptions import AIServiceError

logger = structlog.get_logger()


class BaseAgent:
    """
    Base class for AI extraction agents with retry on invalid JSON responses.
    """

    def __init__(self, tenant_id: str | None = None) -> None:
        self._service = AIService(tenant_id=tenant_id)

    async def _run_with_retry(self, system_prompt: str, user_content: str) -> Any:
        try:
            return await self._service.run_extraction(system_prompt, user_content)
        except AIServiceError as exc:
            logger.warning("ai_extraction_retry", error=str(exc))
        except Exception as exc:
            logger.warning("ai_extraction_retry_unexpected", error=str(exc))

        hardened_prompt = (
            f"{system_prompt}\n\n"
            "RESPONDE SOLO CON JSON ESTRICTO. NO agregues texto, "
            "no uses Markdown, no incluyas explicaciones."
        )
        return await self._service.run_extraction(hardened_prompt, user_content)
