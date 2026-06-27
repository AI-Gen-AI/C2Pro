"""TS-COH-BUD-RECON-001: structured budget clauses for deterministic coherence."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.coherence.models import Clause


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal | int | float):
        return float(value)
    return None


async def build_budget_clauses(
    db: AsyncSession,
    project_id: UUID,
    tenant_id: UUID,
) -> list[Clause]:
    """Build deterministic BUDGET clauses from tenant-scoped procurement BOM rows."""
    bom_stmt = text("""
        SELECT b.id, b.item_name, b.quantity, b.unit_price, b.total_price
        FROM procurement_bom_items b
        JOIN projects p ON b.project_id = p.id
        WHERE b.project_id = CAST(:project_id AS uuid)
          AND p.tenant_id = CAST(:tenant_id AS uuid)
    """)
    bom_result = await db.execute(
        bom_stmt,
        {"project_id": str(project_id), "tenant_id": str(tenant_id)},
    )
    rows = bom_result.fetchall()
    if not rows:
        return []

    clauses: list[Clause] = []
    reconciliation_items: list[dict[str, float | str]] = []
    for row in rows:
        unit_price = _as_float(row.unit_price)
        quantity = _as_float(row.quantity)
        total_price = _as_float(row.total_price)
        if unit_price is None or quantity is None or total_price is None:
            continue

        item_name = str(row.item_name or "")
        clauses.append(
            Clause(
                id=f"bom-{row.id}",
                text=item_name,
                data={
                    "document_type": "budget",
                    "source": "procurement_bom",
                    "category": "BUDGET",
                    "affected_categories": ["BUDGET"],
                    "unit_price": unit_price,
                    "quantity": quantity,
                    "line_total": total_price,
                    "total": total_price,
                },
            )
        )
        reconciliation_items.append({"amount": total_price, "name": item_name})

    contract_stmt = text("""
        SELECT (c.extracted_entities->>'total_amount')::numeric AS amt
        FROM clauses c
        JOIN documents d ON c.document_id = d.id
        JOIN projects p ON d.project_id = p.id
        WHERE d.project_id = CAST(:project_id AS uuid)
          AND p.tenant_id = CAST(:tenant_id AS uuid)
          AND d.document_type::text = 'contract'
          AND c.extracted_entities ? 'total_amount'
        ORDER BY amt DESC
        LIMIT 1
    """)
    contract_result = await db.execute(
        contract_stmt,
        {"project_id": str(project_id), "tenant_id": str(tenant_id)},
    )
    contract_total = _as_float(contract_result.scalar_one_or_none())
    if reconciliation_items and contract_total is not None:
        clauses.append(
            Clause(
                id=f"budget-reconciliation-{project_id}",
                text="Project budget vs contract reconciliation",
                data={
                    "document_type": "budget",
                    "category": "BUDGET",
                    "affected_categories": ["BUDGET"],
                    "budget_items": reconciliation_items,
                    "contract_total": contract_total,
                },
            )
        )

    return clauses
