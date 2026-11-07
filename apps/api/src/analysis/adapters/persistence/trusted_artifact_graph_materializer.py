"""Tenant-scoped materialization of trusted artifacts into the canonical KG.

The ProjectGraph invokes this adapter only after its repository has selected
``trust_state='trusted'`` artifacts.  It deliberately stores identity and
lineage only: no proposed specification, source observation, score, alert, or
generated finding is promoted into the graph here.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import KnowledgeGraphEdgeORM, KnowledgeGraphNodeORM
from src.analysis.domain.contracts import DocumentArtifact
from src.core.tenants.types import TenantId, require_tenant_id
from src.projects.adapters.persistence.models import ProjectORM

_PROJECT_NODE_TYPE = "PROJECT"
_DOCUMENT_NODE_TYPE = "TRUSTED_DOCUMENT"
_TRUSTED_ARTIFACT_RELATION = "HAS_TRUSTED_DOCUMENT_ARTIFACT"


@dataclass(frozen=True)
class KnowledgeGraphMaterialization:
    """Counts written by one idempotent trusted-artifact graph projection."""

    node_count: int
    edge_count: int


class SqlAlchemyTrustedArtifactGraphMaterializer:
    """Upsert trusted document identities and their project relationship.

    The caller owns the surrounding transaction and must set
    ``app.current_tenant``.  The explicit project/tenant lookup is retained in
    addition to RLS so a caller cannot materialize into a project belonging to
    a different tenant when tests or maintenance tooling use a privileged role.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def materialize_trusted_artifacts(
        self,
        *,
        project_id: UUID,
        tenant_id: TenantId,
        artifacts: list[DocumentArtifact],
    ) -> KnowledgeGraphMaterialization:
        tenant_id = require_tenant_id(tenant_id)
        if not artifacts:
            return KnowledgeGraphMaterialization(node_count=0, edge_count=0)
        allowed_project = (
            await self._session.execute(
                select(ProjectORM.id).where(
                    ProjectORM.id == project_id,
                    ProjectORM.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if allowed_project is None:
            raise PermissionError("project is not available to the tenant")

        project_node_id = await self._upsert_node(
            project_id=project_id,
            entity_type=_PROJECT_NODE_TYPE,
            entity_id=project_id,
            label="Project",
            properties={"entity_state": "project_identity"},
        )
        node_count = 1
        edge_count = 0
        seen_document_revisions: dict[UUID, str | None] = {}
        for artifact in artifacts:
            # A trusted artifact without the canonical document UUID cannot be
            # safely joined to the graph.  Fail the transaction rather than
            # fabricate a node identifier or acknowledge the hand-off.
            try:
                document_id = UUID(artifact.document_id)
            except (TypeError, ValueError) as exc:
                raise ValueError("trusted artifact document_id must be a UUID") from exc
            if document_id in seen_document_revisions:
                if seen_document_revisions[document_id] != artifact.document_revision_id:
                    raise ValueError("trusted artifacts disagree on a document revision")
                continue
            seen_document_revisions[document_id] = artifact.document_revision_id

            document_node_id = await self._upsert_node(
                project_id=project_id,
                entity_type=_DOCUMENT_NODE_TYPE,
                entity_id=document_id,
                label=artifact.doc_type,
                properties={
                    "document_id": str(document_id),
                    "document_revision_id": artifact.document_revision_id,
                    "doc_type": artifact.doc_type,
                    "document_category": artifact.document_category,
                    "trust_state": "trusted",
                    "evidence_state": "trusted_artifact_identity_only",
                },
            )
            node_count += 1
            await self._upsert_edge(
                project_id=project_id,
                source_node_id=project_node_id,
                target_node_id=document_node_id,
                properties={
                    "document_revision_id": artifact.document_revision_id,
                    "trust_state": "trusted",
                    "evidence_state": "trusted_artifact_identity_only",
                },
            )
            edge_count += 1

        return KnowledgeGraphMaterialization(node_count=node_count, edge_count=edge_count)

    async def _upsert_node(
        self,
        *,
        project_id: UUID,
        entity_type: str,
        entity_id: UUID,
        label: str,
        properties: dict[str, object],
    ) -> UUID:
        statement = insert(KnowledgeGraphNodeORM).values(
            project_id=project_id,
            entity_type=entity_type,
            entity_id=entity_id,
            label=label,
            properties=properties,
        )
        result = await self._session.execute(
            statement.on_conflict_do_update(
                constraint="kg_nodes_project_entity_unique",
                set_={
                    "label": statement.excluded.label,
                    "properties": statement.excluded.properties,
                },
            ).returning(KnowledgeGraphNodeORM.id)
        )
        return result.scalar_one()

    async def _upsert_edge(
        self,
        *,
        project_id: UUID,
        source_node_id: UUID,
        target_node_id: UUID,
        properties: dict[str, object],
    ) -> None:
        statement = insert(KnowledgeGraphEdgeORM).values(
            project_id=project_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            relationship_type=_TRUSTED_ARTIFACT_RELATION,
            properties=properties,
            confidence=1.0,
        )
        await self._session.execute(
            statement.on_conflict_do_update(
                constraint="kg_edges_unique",
                set_={"properties": statement.excluded.properties},
            )
        )


__all__ = [
    "KnowledgeGraphMaterialization",
    "SqlAlchemyTrustedArtifactGraphMaterializer",
]
