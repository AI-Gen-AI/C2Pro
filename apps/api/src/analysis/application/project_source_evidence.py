"""Read original budget and schedule observations for project decisions.

This is an evidence projection, not an AI prompt, not a WBS/BOM,
and not approval of a monetary or schedule baseline.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID


def summarize_source_units(
    budget_rows: list[Mapping[str, Any]],
    schedule_rows: list[Mapping[str, Any]],
    *,
    max_preview_per_family: int = 40,
) -> dict[str, Any]:
    """Preserve original structured values and provenance without inventing coverage."""
    if max_preview_per_family < 1:
        raise ValueError("INVALID_SOURCE_PREVIEW_LIMIT")
    summary: dict[str, Any] = {
        "state": (
            "SOURCE_OBSERVED_NOT_APPROVED"
            if budget_rows or schedule_rows else "NO_CANONICAL_SOURCE_ROWS"
        ),
        "baseline_approved": False,
        "budget": {},
        "schedule": {},
    }
    for family, rows in (("budget", budget_rows), ("schedule", schedule_rows)):
        examples = []
        for row in rows[:max_preview_per_family]:
            payload = row.get("payload")
            if not isinstance(payload, dict):
                # Unknown provenance is not silently assigned to a source.
                continue
            examples.append({
                "document_id": str(row["document_id"]),
                "revision_id": str(row["revision_id"]),
                "source_locator": str(row["source_locator"]),
                "unit_sha256": str(row["unit_sha256"]),
                "kind": payload.get("kind"),
                "fields": payload,
            })
        summary[family] = {
            "observed_rows": len(rows),
            "preview_rows": examples,
            "truncated": len(rows) > max_preview_per_family,
            "state": "SOURCE_OBSERVED" if rows else "NO_CANONICAL_SOURCE_ROWS",
            "coverage": "NOT_ASSESSED",
            "baseline_approved": False,
        }
    return summary


async def read_project_source_evidence(
    *,
    tenant_id: UUID,
    project_id: UUID,
) -> dict[str, Any]:
    """DB read scoped by tenant and current canonical revision only."""
    from src.core.database import get_session_with_tenant
    from src.documents.application.structured_source_units import (
        load_canonical_source_units,
    )

    async with get_session_with_tenant(tenant_id) as session:
        budget = await load_canonical_source_units(
            session=session, tenant_id=tenant_id, project_id=project_id,
            family="budget",
        )
        schedule = await load_canonical_source_units(
            session=session, tenant_id=tenant_id, project_id=project_id,
            family="schedule",
        )
    return summarize_source_units(budget, schedule)


__all__ = ["read_project_source_evidence", "summarize_source_units"]
