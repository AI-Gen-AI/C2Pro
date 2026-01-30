from __future__ import annotations

from typing import Any, Protocol


class AnalysisOrchestrator(Protocol):
    async def run(self, initial_state: dict[str, Any], thread_id: str) -> dict[str, Any]:
        ...
