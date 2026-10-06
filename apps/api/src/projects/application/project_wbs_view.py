"""The project WBS read model served by GET /projects/{project_id}/wbs.

PC-2a.3 (#897): the live rows are served as before (first-party clients keep working) with an
additive ``authority`` block from the single resolver: LEGACY_UNGOVERNED rows stay readable but
are explicitly unapproved and never count as approved scope; change-set candidates are never
served here (they live only behind the governance APIs). Even an approved baseline confers no
authority on the rows' date / budget columns.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.tenants.types import require_tenant_id
from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
from src.procurement.application.use_cases import GetWBSTreeUseCase, ListWBSItemsUseCase
from src.procurement.domain.models import WBSItem
from src.wbs.adapters.persistence.governance_repository import WBSGovernanceRepository
from src.wbs.domain.governance import AuthorityState, WBSAuthority, wbs_scope_label


def serialize_wbs_item_tree(item: WBSItem) -> dict[str, object]:
    """TS-E2E-FLW-BLK-001: serialize procurement WBS domain rows as a hierarchy."""
    return {
        "id": str(item.id),
        "project_id": str(item.project_id),
        "code": item.code,
        "name": item.name,
        "level": item.level,
        "description": item.description,
        "parent_code": item.parent_code,
        "item_type": item.item_type.value if item.item_type else None,
        "budget_allocated": float(item.budget_allocated)
        if item.budget_allocated is not None
        else None,
        "budget_spent": float(item.budget_spent),
        "planned_start": item.planned_start.isoformat() if item.planned_start else None,
        "planned_end": item.planned_end.isoformat() if item.planned_end else None,
        "actual_start": item.actual_start.isoformat() if item.actual_start else None,
        "actual_end": item.actual_end.isoformat() if item.actual_end else None,
        "source_clause_id": str(item.source_clause_id) if item.source_clause_id else None,
        "version": item.version,
        "metadata": item.wbs_metadata,
        "children": [serialize_wbs_item_tree(child) for child in item.children],
    }


def wbs_authority_view(authority: WBSAuthority) -> dict[str, object]:
    """The authority qualification every WBS reader carries (state from the single resolver)."""
    return {
        "state": authority.state.value,
        "display_state": authority.display_state,
        "approved": authority.approved,
        "scope_label": wbs_scope_label(authority),
        "baseline_id": str(authority.baseline_id) if authority.baseline_id else None,
        "baseline_no": authority.baseline_no,
        "tree_digest": authority.tree_digest,
        "applied_at": authority.applied_at.isoformat() if authority.applied_at else None,
        "draft_exists": authority.draft_exists,
        # Scope authority only: never Schedule (dates) or Cost (budget) authority.
        "dates_schedule_authority": False,
        "budget_cost_authority": False,
    }


def build_wbs_coverage(items: Sequence[object], authority: WBSAuthority | None = None) -> dict[str, object]:
    """TS-E2E-FLW-BLK-001: summarize project WBS evidence coverage.

    The descriptive counts cover every live row. Only an approved baseline counts as approved
    scope; legacy rows are reported apart (PC-2a.3).
    """
    total_items = len(items)
    completed_items = sum(1 for item in items if getattr(item, "actual_end", None) is not None)
    return {
        "total_items": total_items,
        "items_with_budget": sum(
            1 for item in items if getattr(item, "budget_allocated", None) is not None
        ),
        "items_with_dates": sum(
            1
            for item in items
            if getattr(item, "planned_start", None) is not None
            and getattr(item, "planned_end", None) is not None
        ),
        "items_with_alerts": 0,
        "completion_average": 0.0
        if total_items == 0
        else round((completed_items / total_items) * 100, 2),
        "approved_scope_items": total_items if authority is not None and authority.approved else 0,
        "unapproved_legacy_items": total_items
        if authority is not None and authority.state is AuthorityState.LEGACY_UNGOVERNED
        else 0,
    }


async def build_project_wbs_view(session: AsyncSession, project_id: UUID, tenant_id: UUID) -> dict[str, object]:
    """The project's live WBS tree, flat coverage, alerts and authority (resolved once)."""
    scoped = require_tenant_id(tenant_id)
    wbs_repo = SQLAlchemyWBSRepository(session)
    authority = await WBSGovernanceRepository(session).authority(project_id, scoped)
    tree_items = await GetWBSTreeUseCase(wbs_repo).execute(project_id, scoped)
    flat_items = await ListWBSItemsUseCase(wbs_repo).execute(project_id, scoped)
    return {
        "project_id": str(project_id),
        "items": [serialize_wbs_item_tree(item) for item in tree_items],
        "coverage": build_wbs_coverage(flat_items, authority),
        "alerts": [],
        "total_items": len(flat_items),
        "authority": wbs_authority_view(authority),
    }


__all__ = ["build_project_wbs_view", "build_wbs_coverage", "serialize_wbs_item_tree", "wbs_authority_view"]
