"""TS-UD-COH-SCH-002: structured TIME clauses from tenant-scoped WBS schedules."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.coherence.models import Clause


def _as_date_string(value: object) -> str | None:
    """Serialize an explicit WBS schedule date without inventing a value."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return None


async def build_schedule_clauses(
    db: AsyncSession,
    project_id: UUID,
    tenant_id: UUID,
    *,
    max_items: int = 50,
) -> list[Clause]:
    """Build bounded TIME clauses from canonical or legacy tenant-scoped WBS rows."""
    params = {
        "project_id": str(project_id),
        "tenant_id": str(tenant_id),
        "limit": max(0, max_items),
    }
    wbs_nodes_stmt = text("""
        SELECT
            id,
            code,
            name,
            planned_start,
            planned_end,
            status::text AS status,
            metadata->>'predecessor_id' AS predecessor_id,
            'wbs_nodes'::text AS source
        FROM wbs_nodes
        WHERE project_id = CAST(:project_id AS uuid)
          AND tenant_id = CAST(:tenant_id AS uuid)
          AND (planned_start IS NOT NULL OR planned_end IS NOT NULL)
        ORDER BY planned_start ASC NULLS LAST, code ASC
        LIMIT :limit
    """)
    result = await db.execute(wbs_nodes_stmt, params)
    rows = result.fetchall()
    if not rows:
        # Existing document ingestion writes procurement WBS items. The
        # project tenant join preserves tenant isolation until that path is
        # migrated to the canonical RLS-protected wbs_nodes table.
        legacy_stmt = text("""
            SELECT
                w.id,
                w.code,
                w.name,
                w.planned_start,
                w.planned_end,
                COALESCE(w.wbs_metadata->>'status', 'not_started')::text AS status,
                w.wbs_metadata->>'predecessor_id' AS predecessor_id,
                'procurement_wbs_items'::text AS source
            FROM procurement_wbs_items w
            JOIN projects p ON p.id = w.project_id
            WHERE w.project_id = CAST(:project_id AS uuid)
              AND p.tenant_id = CAST(:tenant_id AS uuid)
              AND (w.planned_start IS NOT NULL OR w.planned_end IS NOT NULL)
            ORDER BY w.planned_start ASC NULLS LAST, w.code ASC
            LIMIT :limit
        """)
        result = await db.execute(legacy_stmt, params)
        rows = result.fetchall()
    if not rows:
        return []

    clauses: list[Clause] = []
    schedule_items: list[dict[str, Any]] = []
    milestones: list[dict[str, str]] = []
    for row in rows:
        start_date = _as_date_string(row.planned_start)
        end_date = _as_date_string(row.planned_end)
        item_id = str(row.code or row.id)
        item: dict[str, Any] = {
            # Parsers express dependencies by WBS code, not database UUID.
            "id": item_id,
            "wbs_node_id": str(row.id),
            "code": str(row.code),
            "name": str(row.name),
            "start_date": start_date,
            "end_date": end_date,
            "status": str(row.status),
            # WBS parent_id is hierarchy, not a scheduling predecessor.
            "predecessor_id": str(row.predecessor_id) if row.predecessor_id else None,
        }
        schedule_items.append(item)
        if end_date:
            milestones.append(
                {
                    "id": item["id"],
                    "wbs_node_id": item["wbs_node_id"],
                    "name": item["name"],
                    "date": end_date,
                }
            )
        clauses.append(
            Clause(
                id=f"{row.source}-schedule-{row.id}",
                text=f"{item['name']}: {start_date or 'unscheduled'} to {end_date or 'unscheduled'}",
                data={
                    "document_type": "schedule",
                    "source": str(row.source),
                    "category": "TIME",
                    "affected_categories": ["TIME"],
                    **item,
                },
            )
        )

    clauses.append(
        Clause(
            id=f"schedule-timeline-{project_id}",
            text="Project schedule timeline from WBS activities",
            data={
                "document_type": "schedule",
                "source": "wbs_schedule",
                "category": "TIME",
                "affected_categories": ["TIME"],
                "schedule_items": schedule_items,
                "milestones": milestones,
            },
        )
    )
    return clauses
