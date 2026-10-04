"""Clause impact resolver: persisted relationships only (PR-C2).

Follows the foreign keys that already point at ``clauses.id``; never text
similarity, never generated labels. The source clause must provably be the
earlier revision's own clause (same document, bound to that revision, or
unbound in a revision with no parent) before any relationship is reported.

Direct links:   alerts.source_clause_id, stakeholders.source_clause_id,
                wbs_nodes.source_clause_id, procurement_bom_items.contract_clause_id.
Direct, unknown strength: alerts.related_clause_ids -- an aggregated list of
                "related" clauses a rule cited, so it proposes (CANDIDATE) only.
Indirect (one hop): stakeholders.source_clause_id -> stakeholder_wbs_raci -> wbs_nodes.
The RACI hop is generated, so its link confidence is unknown.

Every target must belong to the verified clause's tenant AND project; a
reference from another project is never reported.

The legacy ``procurement_wbs_items`` mapping is not read (ADR-025).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import any_, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import Alert
from src.documents.adapters.persistence.models import ClauseORM
from src.documents.domain.clause_revision_binding import revision_id_from_extracted_entities
from src.procurement.adapters.persistence.models import BOMItemORM
from src.shared_kernel.enums import AlertStatus
from src.stakeholders.adapters.persistence.models import StakeholderORM, StakeholderWBSRaciORM
from src.temporal.adapters.persistence.models import DocumentRevisionORM
from src.temporal.application.impact_assessment import ResolvedLink, ResolverResult
from src.temporal.domain.entity_ref import TemporalEntityRef
from src.temporal.domain.impact import ImpactRelationship, ImpactTarget
from src.wbs.adapters.persistence.models import WBSNodeORM

# An alert still acting on the earlier interpretation of the clause.
_LIVE_ALERT_STATUSES = frozenset({AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED})


def _status(value: object) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _direct(via: str, *, established: bool = True) -> ImpactRelationship:
    return ImpactRelationship(kind="direct", via=via, link_confidence=1.0 if established else None)


class SqlAlchemyClauseImpactResolver:
    entity_type = "clause"

    def __init__(self, session: AsyncSession, *, tenant_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def _verified_clause(
        self, source: TemporalEntityRef
    ) -> tuple[ClauseORM | None, str | None]:
        try:
            clause_id = UUID(str(source.entity_id))
        except ValueError:
            return None, "the source clause identifier is not a persisted id"
        clause = (
            await self._session.execute(
                select(ClauseORM).where(
                    ClauseORM.id == clause_id, ClauseORM.tenant_id == self._tenant_id
                )
            )
        ).scalar_one_or_none()
        if clause is None:
            return None, "the source clause is no longer persisted"
        if clause.document_id != source.document_id:
            return None, "the persisted clause belongs to another document"
        revision = (
            await self._session.execute(
                select(DocumentRevisionORM).where(
                    DocumentRevisionORM.revision_id == source.revision_id,
                    DocumentRevisionORM.tenant_id == self._tenant_id,
                )
            )
        ).scalar_one_or_none()
        if revision is None or revision.document_id != source.document_id:
            return None, "the source revision is not a revision of this document"
        bound = revision_id_from_extracted_entities(clause.extracted_entities)
        if bound == revision.revision_id or (bound is None and revision.parent_revision_id is None):
            return clause, None
        return None, "the persisted clause cannot be proven to belong to the source revision"

    async def _alert_links(self, clause_id: UUID, project_id: UUID) -> list[ResolvedLink]:
        rows = (
            (
                await self._session.execute(
                    select(Alert)
                    .where(
                        Alert.tenant_id == self._tenant_id,
                        Alert.project_id == project_id,
                        or_(
                            Alert.source_clause_id == clause_id,
                            literal(clause_id) == any_(Alert.related_clause_ids),
                        ),
                    )
                    .order_by(Alert.created_at.asc(), Alert.id.asc())
                )
            )
            .scalars()
            .all()
        )
        return [
            ResolvedLink(
                target=ImpactTarget(
                    entity_type="alert",
                    entity_id=alert.id,
                    label=alert.title,
                    status=_status(alert.status),
                    potentially_stale=alert.status in _LIVE_ALERT_STATUSES,
                ),
                relationship=(
                    _direct("alerts.source_clause_id")
                    if alert.source_clause_id == clause_id
                    else _direct("alerts.related_clause_ids", established=False)
                ),
            )
            for alert in rows
        ]

    async def resolve(self, source: TemporalEntityRef) -> ResolverResult:
        clause, reason = await self._verified_clause(source)
        if clause is None:
            return ResolverResult(links=[], source_verified=False, reason=reason)
        clause_id = clause.id
        project_id = clause.project_id
        links = await self._alert_links(clause_id, project_id)

        stakeholders = (
            (
                await self._session.execute(
                    select(StakeholderORM)
                    .where(
                        StakeholderORM.tenant_id == self._tenant_id,
                        StakeholderORM.project_id == project_id,
                        StakeholderORM.source_clause_id == clause_id,
                    )
                    .order_by(StakeholderORM.id.asc())
                )
            )
            .scalars()
            .all()
        )
        links += [
            ResolvedLink(
                target=ImpactTarget(
                    entity_type="stakeholder", entity_id=row.id, label=row.name or row.role
                ),
                relationship=_direct("stakeholders.source_clause_id"),
            )
            for row in stakeholders
        ]

        wbs_nodes = (
            (
                await self._session.execute(
                    select(WBSNodeORM)
                    .where(
                        WBSNodeORM.tenant_id == self._tenant_id,
                        WBSNodeORM.project_id == project_id,
                        WBSNodeORM.source_clause_id == clause_id,
                    )
                    .order_by(WBSNodeORM.code.asc(), WBSNodeORM.id.asc())
                )
            )
            .scalars()
            .all()
        )
        links += [
            ResolvedLink(
                target=ImpactTarget(
                    entity_type="wbs_node",
                    entity_id=row.id,
                    label=f"{row.code} {row.name}",
                    status=_status(row.status),
                ),
                relationship=_direct("wbs_nodes.source_clause_id"),
            )
            for row in wbs_nodes
        ]

        # procurement_bom_items has no tenant_id: scope it by the verified clause's project.
        bom_items = (
            (
                await self._session.execute(
                    select(BOMItemORM)
                    .where(
                        BOMItemORM.project_id == project_id,
                        BOMItemORM.contract_clause_id == clause_id,
                    )
                    .order_by(BOMItemORM.id.asc())
                )
            )
            .scalars()
            .all()
        )
        links += [
            ResolvedLink(
                target=ImpactTarget(entity_type="bom_item", entity_id=row.id, label=row.item_name),
                relationship=_direct("procurement_bom_items.contract_clause_id"),
            )
            for row in bom_items
        ]

        stakeholder_ids = [row.id for row in stakeholders]
        if stakeholder_ids:
            direct_wbs = {row.id for row in wbs_nodes}
            hop_rows = (
                (
                    await self._session.execute(
                        select(WBSNodeORM)
                        .join(
                            StakeholderWBSRaciORM,
                            StakeholderWBSRaciORM.wbs_item_id == WBSNodeORM.id,
                        )
                        .where(
                            StakeholderWBSRaciORM.tenant_id == self._tenant_id,
                            StakeholderWBSRaciORM.project_id == project_id,
                            StakeholderWBSRaciORM.stakeholder_id.in_(stakeholder_ids),
                            WBSNodeORM.tenant_id == self._tenant_id,
                            WBSNodeORM.project_id == project_id,
                        )
                        .distinct()
                        .order_by(WBSNodeORM.code.asc(), WBSNodeORM.id.asc())
                    )
                )
                .scalars()
                .all()
            )
            links += [
                ResolvedLink(
                    target=ImpactTarget(
                        entity_type="wbs_node",
                        entity_id=row.id,
                        label=f"{row.code} {row.name}",
                        status=_status(row.status),
                    ),
                    relationship=ImpactRelationship(
                        kind="indirect",
                        via="stakeholders.source_clause_id>stakeholder_wbs_raci",
                        link_confidence=None,
                    ),
                )
                for row in hop_rows
                if row.id not in direct_wbs
            ]

        return ResolverResult(
            links=links,
            source_verified=True,
            reason=None if links else "no persisted relationship to any project entity",
        )


__all__ = ["SqlAlchemyClauseImpactResolver"]
