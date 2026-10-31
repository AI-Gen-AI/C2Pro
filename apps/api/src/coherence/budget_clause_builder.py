"""TS-COH-BUD-RECON-001 / #860: budget-document facts for deterministic coherence."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.coherence.domain.budget_line_availability import STRUCTURED_BUDGET_SOURCE_UNAVAILABLE
from src.coherence.models import Clause
from src.documents.domain.revision_declarations import STATED_TOTAL_BY_REVISION_KEY
from src.temporal.adapters.persistence.current_revision_sql import (
    canonical_clause_in_current_scope,
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
      AND {canonical_clause_in_current_scope("c", "cur")}
    ORDER BY amt DESC
    LIMIT 1
""")


async def load_contract_total(db: AsyncSession, project_id: UUID, tenant_id: UUID) -> float | None:
    """The largest stated contract total among the project's current contract clauses."""
    result = await db.execute(
        _CONTRACT_TOTAL_SQL, {"project_id": str(project_id), "tenant_id": str(tenant_id)}
    )
    return _as_float(result.scalar_one_or_none())


# The budget's declared total AND its denominations, from ONE row: the entry the worker recorded
# for the budget document's trusted-current revision (C3a authority, the same predicate the
# contract totals use). A proposed or rejected re-upload, a revision without a verifiable stamp and
# a document whose current revision declares no total all yield no row: UNKNOWN, never the latest
# ingested figure and never an older revision's. A revision that is only a pending proposal does
# not count (B1 canonical-alert spec §3: PROPOSED evidence never moves canonical alerts or score).
_BUDGET_DECLARATION_SQL = text(f"""
    SELECT (e.entry->>'total')::numeric AS amt,
           e.entry->'currencies' AS currencies
    FROM documents d
    CROSS JOIN LATERAL {current_revision_lateral("d.id", "d.tenant_id")} AS cur
    CROSS JOIN LATERAL (
        SELECT d.document_metadata->'{STATED_TOTAL_BY_REVISION_KEY}'->(cur.revision_id::text) AS entry
    ) AS e
    WHERE d.project_id = CAST(:project_id AS uuid)
      AND d.tenant_id = CAST(:tenant_id AS uuid)
      AND d.document_type::text = 'budget'
      -- ``canonical``: trusted, or resolved with no pending proposal (one definition for the
      -- contract and the budget side, #1133).
      AND cur.canonical
      AND e.entry->>'revision_id' = cur.revision_id::text
      AND jsonb_typeof(e.entry->'total') = 'number'
    ORDER BY d.updated_at DESC NULLS LAST, d.created_at DESC NULLS LAST
    LIMIT 1
""")

# Denominations stated alongside each side's total. Contract currencies count
# only when the clause names them explicitly (ingestion's EUR default does not).
_CONTRACT_CURRENCIES_SQL = text(f"""
    SELECT array_agg(DISTINCT upper(btrim(c.extracted_entities->>'currency')))
    FROM clauses c
    JOIN documents d ON c.document_id = d.id
    JOIN projects p ON d.project_id = p.id
    CROSS JOIN LATERAL {current_revision_lateral("c.document_id", "c.tenant_id")} AS cur
    WHERE d.project_id = CAST(:project_id AS uuid)
      AND p.tenant_id = CAST(:tenant_id AS uuid)
      AND d.document_type::text = 'contract'
      AND c.extracted_entities ? 'total_amount'
      AND c.extracted_entities->>'currency_source' = 'explicit'
      AND length(btrim(coalesce(c.extracted_entities->>'currency', ''))) > 0
      AND {canonical_clause_in_current_scope("c", "cur")}
""")


def _currency_list(value: Any) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    return sorted({v.strip().upper() for v in value if isinstance(v, str) and v.strip()})


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
    declaration = (await db.execute(_BUDGET_DECLARATION_SQL, params)).first()
    stated_total = _as_float(declaration[0]) if declaration is not None else None
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
        # Generic coverage marker: routing this budget-typed clause (or a
        # total-level rule pass) must not make BUDGET read as assessed / clean.
        "assessment_unavailable": {"BUDGET": STRUCTURED_BUDGET_SOURCE_UNAVAILABLE},
    }
    contract_total = await load_contract_total(db, project_id, tenant_id)
    if contract_total is not None:
        data["contract_total"] = contract_total
        # Each side keeps its own denomination: one shared "currency" key on this
        # single clause could never reveal a EUR contract vs a USD budget.
        budget_currencies = _currency_list(declaration[1] if declaration is not None else None)
        contract_currencies = _currency_list(
            (await db.execute(_CONTRACT_CURRENCIES_SQL, params)).scalar_one_or_none()
        )
        if budget_currencies:
            data["budget_currencies"] = budget_currencies
        if contract_currencies:
            data["contract_currencies"] = contract_currencies
    return [
        Clause(
            id=f"budget-reconciliation-{project_id}",
            text="Project budget vs contract reconciliation",
            data=data,
        )
    ]
