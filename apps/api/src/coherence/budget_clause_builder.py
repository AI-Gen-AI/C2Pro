"""TS-COH-BUD-RECON-001 / #860: budget-document facts for deterministic coherence."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.coherence.domain.budget_line_availability import STRUCTURED_BUDGET_SOURCE_UNAVAILABLE
from src.coherence.models import Clause
from src.temporal.adapters.persistence.current_revision_sql import (
    clause_in_current_scope,
    current_revision_lateral,
)


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal | int | float):
        return float(value)
    return None


# Lane C / C3a: the contract total comes only from each contract's trusted-current
# revision -- a PROPOSED or REJECTED V2 can never move it, and V1+V2 never mix.
_CONTRACT_TOTAL_SQL = text(f"""
    SELECT (c.extracted_entities->>'total_amount')::numeric AS amt
    FROM clauses c
    JOIN documents d ON c.document_id = d.id
    JOIN projects p ON d.project_id = p.id
    CROSS JOIN LATERAL {current_revision_lateral("c.document_id", "c.tenant_id")} AS cur
    WHERE d.project_id = CAST(:project_id AS uuid)
      AND p.tenant_id = CAST(:tenant_id AS uuid)
      AND d.document_type::text = 'contract'
      AND c.extracted_entities ? 'total_amount'
      AND {clause_in_current_scope("c", "cur")}
    ORDER BY amt DESC
    LIMIT 1
""")


async def load_contract_total(db: AsyncSession, project_id: UUID, tenant_id: UUID) -> float | None:
    """The largest stated contract total among the project's current contract clauses."""
    result = await db.execute(
        _CONTRACT_TOTAL_SQL, {"project_id": str(project_id), "tenant_id": str(tenant_id)}
    )
    return _as_float(result.scalar_one_or_none())


_STATED_TOTAL_SQL = text("""
    SELECT (d.document_metadata->>'stated_total')::numeric AS amt
    FROM documents d
    JOIN projects p ON d.project_id = p.id
    WHERE d.project_id = CAST(:project_id AS uuid)
      AND p.tenant_id = CAST(:tenant_id AS uuid)
      AND d.document_type::text = 'budget'
      AND d.document_metadata ? 'stated_total'
    ORDER BY d.updated_at DESC NULLS LAST, d.created_at DESC NULLS LAST
    LIMIT 1
""")


async def build_budget_clauses(
    db: AsyncSession,
    project_id: UUID,
    tenant_id: UUID,
) -> list[Clause]:
    """Budget-document facts for deterministic coherence -- never the BOM table (#860).

    The procurement BOM is a mixed legacy object (manual procurement rows,
    historical budget-derived rows, procurement edits), not budget truth, so no
    BOM row becomes a budget line and no line set is assembled from it: the rules
    that need structured budget lines (DET-BUD-LINEITEM / SUM / INTERNAL) are not
    evaluated, and the clause says so explicitly.

    What IS independently available is kept: the budget document's own declared
    total (and the contract total) reach the total-level rules that need nothing
    else -- no longer gated on BOM rows happening to exist. ``stated_total`` is a
    total, not a line set; no line item is derived from it.
    """
    params = {"project_id": str(project_id), "tenant_id": str(tenant_id)}
    stated_total = _as_float((await db.execute(_STATED_TOTAL_SQL, params)).scalar_one_or_none())
    if stated_total is None:
        return []

    data: dict[str, Any] = {
        "document_type": "budget",
        "source": "budget_document_metadata",
        "category": "BUDGET",
        "affected_categories": ["BUDGET"],
        "stated_total": stated_total,
        "budget_line_items": "unavailable",
        "budget_line_items_reason": STRUCTURED_BUDGET_SOURCE_UNAVAILABLE,
    }
    contract_total = await load_contract_total(db, project_id, tenant_id)
    if contract_total is not None:
        data["contract_total"] = contract_total
    return [
        Clause(
            id=f"budget-reconciliation-{project_id}",
            text="Project budget vs contract reconciliation",
            data=data,
        )
    ]
