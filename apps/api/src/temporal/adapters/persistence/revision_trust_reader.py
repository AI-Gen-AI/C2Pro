"""Read the #714 trust state of a document's artifacts, per bound revision.

Read-only; the #714 ``document_artifacts`` table stays the only trust
authority. One bounded query (distinct revision/state pairs of one document in
one tenant). An artifact without a revision binding is never attributed to a
revision; a TRUSTED one is only reported as ``unbound_trusted``.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import DocumentArtifactORM
from src.analysis.domain.trust import TrustState
from src.temporal.ports.revision_trust_reader import RevisionTrustEvidence


class SqlAlchemyRevisionTrustReader:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def read(self, *, tenant_id: UUID, document_id: UUID) -> RevisionTrustEvidence:
        rows = (
            await self._session.execute(
                select(DocumentArtifactORM.document_revision_id, DocumentArtifactORM.trust_state)
                .where(
                    DocumentArtifactORM.tenant_id == tenant_id,
                    DocumentArtifactORM.document_id == document_id,
                )
                .distinct()
            )
        ).all()
        states: dict[UUID, set[str]] = {}
        unbound_trusted = False
        for revision_id, trust_state in rows:
            if revision_id is None:
                unbound_trusted = unbound_trusted or trust_state == TrustState.TRUSTED.value
                continue
            states.setdefault(revision_id, set()).add(str(trust_state))
        return RevisionTrustEvidence(
            states_by_revision={rev: frozenset(values) for rev, values in states.items()},
            unbound_trusted=unbound_trusted,
        )


__all__ = ["SqlAlchemyRevisionTrustReader"]
