"""The canonical trusted-current revision resolver (Lane C / C3a).

One bounded query per document, executing exactly the SQL rule every other
reader embeds (``current_revision_sql``). Read-only.
"""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession

from src.temporal.adapters.persistence.current_revision_sql import current_revision_lateral
from src.temporal.domain.current_revision import CurrentRevision, CurrentRevisionStatus

_RESOLVE_SQL = text(
    f"""
    SELECT d.document_id, cur.revision_id, cur.resolved, cur.trusted, cur.single_revision
    FROM unnest(CAST(:document_ids AS uuid[])) AS d(document_id)
    CROSS JOIN LATERAL {current_revision_lateral("d.document_id", "CAST(:tenant_id AS uuid)")} AS cur
    """
).bindparams(bindparam("document_ids", type_=ARRAY(PGUUID(as_uuid=True))))


class SqlAlchemyCurrentRevisionResolver:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve(self, *, tenant_id: UUID, document_id: UUID) -> CurrentRevision:
        return (await self.resolve_many(tenant_id=tenant_id, document_ids=[document_id]))[
            document_id
        ]

    async def resolve_many(
        self, *, tenant_id: UUID, document_ids: Iterable[UUID]
    ) -> dict[UUID, CurrentRevision]:
        ids = list(dict.fromkeys(document_ids))
        if not ids:
            return {}
        rows = (
            await self._session.execute(
                _RESOLVE_SQL, {"document_ids": ids, "tenant_id": str(tenant_id)}
            )
        ).all()
        return {row.document_id: _current(row) for row in rows}


def _current(row: object) -> CurrentRevision:
    if getattr(row, "trusted", False):
        status = CurrentRevisionStatus.TRUSTED
    elif getattr(row, "resolved", False):
        status = CurrentRevisionStatus.SINGLE_REVISION
    else:
        status = CurrentRevisionStatus.UNRESOLVED
    return CurrentRevision(
        document_id=row.document_id,  # type: ignore[attr-defined]
        status=status,
        revision_id=row.revision_id if status is not CurrentRevisionStatus.UNRESOLVED else None,  # type: ignore[attr-defined]
        single_revision=bool(row.single_revision),  # type: ignore[attr-defined]
    )


__all__ = ["SqlAlchemyCurrentRevisionResolver"]
