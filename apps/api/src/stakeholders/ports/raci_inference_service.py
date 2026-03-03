"""
I10 RACI inference service port.

Refers to Suite ID: TS-I10-STK-PORT-001.
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID


class IRaciInferenceService(Protocol):
    """Port contract for I10 inference gateway used by application services."""

    async def generate_raci_matrix(
        self,
        contract_statements: list[dict[str, str]],
        tenant_id: UUID,
        project_id: UUID | None = None,
    ) -> tuple[list[Any], list[dict[str, Any]]]:
        ...
