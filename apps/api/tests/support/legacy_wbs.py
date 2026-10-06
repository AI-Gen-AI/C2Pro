"""Seed LEGACY_UNGOVERNED live WBS rows for tests (PC-2a.2 #896, ADR-029).

No application path writes governed live WBS content any more: the repository refuses it
(``WBS_GOVERNANCE_REQUIRED``) and the ``wbs_nodes`` database guard only admits the governed
approve = apply transaction. Legacy rows therefore exist only as historical data, so tests load
them the way a data migration would: as the (superuser) test owner with triggers and FK checks
off (``session_replication_role = replica``) for the duration of the seed, in the caller's
transaction. Never use this in application code.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import Table, bindparam, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
from src.procurement.domain.models import WBSItem
from src.shared_kernel.enums import WBSItemType
from src.wbs.adapters.persistence.models import WBSNodeORM


@asynccontextmanager
async def legacy_wbs_writes(session: AsyncSession) -> AsyncIterator[None]:
    """Out-of-band legacy data load: triggers (incl. the governance guard) and FK checks off."""
    await session.execute(text("SET LOCAL session_replication_role = replica"))
    try:
        yield
        await session.flush()
    finally:
        await session.execute(text("SET LOCAL session_replication_role = origin"))


@asynccontextmanager
async def governed_apply_state(session: AsyncSession, tenant_id: UUID, project_id: UUID) -> AsyncIterator[None]:
    """The database state of an in-flight approve = apply, for structural-constraint tests.

    Loads (out of band) a SUBMITTED first-baseline change set, THIS transaction's baseline row for
    it and the apply correlation, so the ``wbs_nodes`` guard admits direct structural writes and
    every other trigger and constraint (cycles, depth caches, deferred uniqueness, parent FKs)
    runs exactly as it does under a real apply. The authority rows are removed again on exit, so
    the caller's commit only runs the structural deferred checks. Never use in application code.
    """
    change_set, baseline, approver = uuid4(), uuid4(), uuid4()
    digest = "sha256:" + "0" * 64
    params = {"cs": change_set, "bl": baseline, "t": tenant_id, "p": project_id, "u": approver, "d": digest}
    async with legacy_wbs_writes(session):
        await session.execute(text(
            "INSERT INTO wbs_change_sets (id, tenant_id, project_id, origin, entry_mode, title, created_by, "
            "created_by_kind, status, revision, submitted_revision, submitted_digest, submitted_by, submitted_at) "
            "VALUES (:cs, :t, :p, 'manual', 'GENERATE', 'structural test', :u, 'human', 'SUBMITTED', 1, 1, :d, :u, now())"),
            params)
        await session.execute(text(
            "INSERT INTO wbs_baselines (id, tenant_id, project_id, baseline_no, source_change_set_id, tree_digest, "
            "change_set_digest, node_count, approved_by, approved_by_kind) VALUES "
            "(:bl, :t, :p, 1, :cs, :d, :d, 0, :u, 'human')"), params)
    await session.execute(text("SELECT set_config('c2pro.wbs_governed_apply', :c, true)"), {"c": str(change_set)})
    yield  # on an error the caller rolls back, and these out-of-band rows go with it
    await session.flush()
    await session.execute(text("SELECT set_config('c2pro.wbs_governed_apply', '', true)"))
    async with legacy_wbs_writes(session):
        await session.execute(text("DELETE FROM wbs_baselines WHERE id = :bl"), params)
        await session.execute(text("DELETE FROM wbs_change_sets WHERE id = :cs"), params)


async def seed_legacy_wbs(session: AsyncSession, tenant_id: UUID, items: Sequence[WBSItem]) -> list[WBSItem]:
    """Insert ``items`` as legacy live rows of their projects; returns them as read back.

    Ids are minted (an item's own ``id`` only links children in the same batch); parents resolve
    by ``parent_id`` (batch or existing row) or ``parent_code``; ``sort_order`` places a node
    among its siblings; the nested-set caches are rebuilt like the repository does.
    """
    repo = SQLAlchemyWBSRepository(session)
    minted = {item.id: uuid4() for item in items}
    by_code: dict[tuple[UUID, str], UUID] = {(item.project_id, item.code): minted[item.id] for item in items}
    async with legacy_wbs_writes(session):
        orms = [
            repo._new_orm(item, node_id=minted[item.id], tenant_id=tenant_id, position=position)  # noqa: SLF001
            for position, item in enumerate(items)
        ]
        session.add_all(orms)
        await session.flush()
        links: list[dict[str, Any]] = []
        positions: dict[UUID, dict[UUID, int]] = {}
        for item in items:
            node_id = minted[item.id]
            parent: UUID | None = None
            if item.parent_id is not None:
                parent = minted.get(item.parent_id, item.parent_id)
            elif item.parent_code:
                parent = by_code.get((item.project_id, item.parent_code)) or await session.scalar(
                    text("SELECT id FROM wbs_nodes WHERE project_id = :p AND code = :c"),
                    {"p": item.project_id, "c": item.parent_code},
                )
                if parent is None:
                    raise ValueError(f"legacy seed: unknown parent code {item.parent_code!r}")
            if parent is not None:
                links.append({"b_id": node_id, "b_parent": parent})
            if item.sort_order is not None:
                positions.setdefault(item.project_id, {})[node_id] = item.sort_order
        if links:
            table = cast(Table, WBSNodeORM.__table__)
            await session.execute(
                update(table).where(table.c.id == bindparam("b_id")).values(parent_id=bindparam("b_parent")),
                links,
                execution_options={"synchronize_session": False},
            )
        for project_id in {item.project_id for item in items}:
            await repo._rebuild(project_id, tenant_id, positions.get(project_id))  # noqa: SLF001
    seeded = [await repo.get_by_id(minted[item.id], tenant_id) for item in items]
    return [item for item in seeded if item is not None]


async def seed_legacy_from_dicts(session: AsyncSession, project_id: UUID, items: Sequence[dict[str, Any]],
                                 tenant_id: UUID) -> list[WBSItem]:
    """Legacy rows from extraction-shaped dicts (the pre-PC-2a.2 ``bulk_create_from_dicts`` mapping)."""

    def _decimal(value: Any) -> Decimal | None:
        try:
            return None if value is None else Decimal(str(value))
        except Exception:  # noqa: BLE001 - mirrors the historical lenient parsing
            return None

    def _datetime(value: Any) -> datetime | None:
        if value is None or isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            return None

    wbs_items: list[WBSItem] = []
    for item in items:
        code = str(item.get("code") or "").strip() or f"T{len(wbs_items) + 1}"
        raw_type = str(item.get("item_type") or "").lower()
        wbs_items.append(WBSItem(
            project_id=project_id, code=code, name=str(item.get("name") or "WBS Item"),
            description=item.get("description"), level=code.count(".") + 1,
            parent_code=item.get("parent_code"),
            item_type=next((t for t in WBSItemType if t.value == raw_type), None),
            budget_allocated=_decimal(item.get("budget_allocated")),
            planned_start=_datetime(item.get("planned_start")), planned_end=_datetime(item.get("planned_end")),
            wbs_metadata={"confidence": item.get("confidence"), "raw": item},
        ))
    return await seed_legacy_wbs(session, tenant_id, wbs_items)


async def seed_legacy_rows(session: AsyncSession, tenant_id: UUID, project_id: UUID, count: int,
                           *, prefix: str = "SCH") -> list[UUID]:
    """``count`` flat legacy rows (the production LEGACY_UNGOVERNED shape); returns their ids."""
    seeded = await seed_legacy_wbs(session, tenant_id, [
        WBSItem(project_id=project_id, code=f"{prefix}-{index:03d}", name=f"Schedule activity {index}", level=1)
        for index in range(1, count + 1)
    ])
    return [item.id for item in seeded]


__all__ = ["governed_apply_state", "legacy_wbs_writes", "seed_legacy_from_dicts", "seed_legacy_rows", "seed_legacy_wbs"]
