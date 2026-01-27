from __future__ import annotations

from typing import Any, Protocol


class IAIClient(Protocol):
    async def extract_json(
        self,
        system_prompt: str,
        user_content: str,
        task_type: str,
    ) -> Any:
        ...
