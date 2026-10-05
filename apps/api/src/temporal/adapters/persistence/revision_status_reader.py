"""Read-only revision status for the What Changed surface (Lane C / C3b-2).

Every query carries an explicit tenant + project + document scope:
``system_recovery.trusted_projection_index`` is not under RLS, so the scope is
enforced here, not delegated. Nothing is written.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.temporal.adapters.persistence.current_revision_resolver import (
    SqlAlchemyCurrentRevisionResolver,
)
from src.temporal.application.revision_status import RevisionStatus, materialization_from_row
from src.temporal.domain.current_revision import CurrentRevisionStatus

_REVISION_SQL = text(
    """
    SELECT r.rev_no
      FROM document_revisions r
     WHERE r.revision_id = cast(:revision_id as uuid)
       AND r.document_id = cast(:document_id as uuid)
       AND r.project_id = cast(:project_id as uuid)
       AND r.tenant_id = cast(:tenant_id as uuid)
    """
)

# The artifact that speaks for the revision: its active trusted artifact when it
# has one, else the newest artifact bound to it (proposed / rejected / superseded).
_ARTIFACT_SQL = text(
    """
    SELECT a.artifact_id, a.artifact_version, a.trust_state,
           o.materialization_state, o.materialization_detail
      FROM document_artifacts a
      LEFT JOIN system_recovery.trusted_projection_index o
        ON o.artifact_id = a.artifact_id
       AND o.tenant_id = a.tenant_id
       AND o.project_id = a.project_id
       AND o.document_id = a.document_id
     WHERE a.tenant_id = cast(:tenant_id as uuid)
       AND a.project_id = cast(:project_id as uuid)
       AND a.document_id = cast(:document_id as uuid)
       AND a.document_revision_id = cast(:revision_id as uuid)
     ORDER BY (a.trust_state = 'trusted' AND a.lifecycle_status = 'active') DESC,
              a.artifact_version DESC, a.created_at DESC
     LIMIT 1
    """
)


class SqlAlchemyRevisionStatusReader:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def read(
        self, *, tenant_id: UUID, project_id: UUID, document_id: UUID, revision_id: UUID
    ) -> RevisionStatus | None:
        params = {
            "tenant_id": str(tenant_id),
            "project_id": str(project_id),
            "document_id": str(document_id),
            "revision_id": str(revision_id),
        }
        revision = (await self._session.execute(_REVISION_SQL, params)).first()
        if revision is None:
            return None
        artifact = (await self._session.execute(_ARTIFACT_SQL, params)).first()
        current = await SqlAlchemyCurrentRevisionResolver(self._session).resolve(
            tenant_id=tenant_id, document_id=document_id
        )
        is_current = (
            current.status is not CurrentRevisionStatus.UNRESOLVED
            and current.revision_id == revision_id
        )
        return RevisionStatus(
            revision_id=revision_id,
            rev_no=int(revision.rev_no),
            trust_state=str(artifact.trust_state) if artifact is not None else None,
            artifact_id=artifact.artifact_id if artifact is not None else None,
            artifact_version=int(artifact.artifact_version) if artifact is not None else None,
            is_current=is_current,
            current_revision_id=current.revision_id,
            current_basis=current.status.value,
            materialization=(
                materialization_from_row(artifact.materialization_state, artifact.materialization_detail)
                if artifact is not None
                else None
            ),
        )


__all__ = ["SqlAlchemyRevisionStatusReader"]
