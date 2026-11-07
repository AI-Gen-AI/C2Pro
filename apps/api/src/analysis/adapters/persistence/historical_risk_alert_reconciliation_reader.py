"""SELECT-only, fail-closed input reader for historical RISK reconciliation.

The legacy ``analyses`` table has no document or revision identity, and the
legacy N4/N17 RISK writer does not persist ``affected_entities.documents``.
Consequently this reader must not attach those alerts to the selected V2
artifact.  It returns the verified artifact snapshot and no historical
analyses; the pure planner then emits ``PLAN_BLOCKED`` (``NOT_ENOUGH_EVIDENCE``)
instead of inventing historical provenance.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import DocumentArtifactORM
from src.analysis.application.historical_risk_alert_reconciliation import (
    ReconciliationInput,
    TrustedArtifactSnapshot,
)
from src.analysis.application.historical_risk_alert_reconciliation_reader import (
    ReconciliationReadScope,
    ReconciliationScopeNotAuthorized,
)
from src.projects.adapters.persistence.models import ProjectORM


class SqlAlchemyHistoricalRiskAlertReconciliationReader:
    """Build a planner input using only persisted, tenant-scoped facts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def assemble(self, scope: ReconciliationReadScope) -> ReconciliationInput:
        # Check project tenancy before looking up the artifact, so an artifact
        # selector never discloses data across tenant boundaries.
        project = await self._session.scalar(
            select(ProjectORM.id).where(
                ProjectORM.id == scope.project_id,
                ProjectORM.tenant_id == scope.tenant_id,
            )
        )
        if project is None:
            raise ReconciliationScopeNotAuthorized("PROJECT_TENANT_MISMATCH")

        artifact = await self._session.scalar(
            select(DocumentArtifactORM).where(
                DocumentArtifactORM.artifact_id == scope.artifact_id,
                DocumentArtifactORM.tenant_id == scope.tenant_id,
                DocumentArtifactORM.project_id == scope.project_id,
                DocumentArtifactORM.document_id == scope.document_id,
                DocumentArtifactORM.document_revision_id == scope.revision_id,
            )
        )
        if artifact is None:
            raise ReconciliationScopeNotAuthorized("ARTIFACT_SCOPE_MISMATCH")

        payload = artifact.payload if isinstance(artifact.payload, Mapping) else {}
        extracted_risks = payload.get("extracted_risks")
        risks: tuple[Mapping[str, object], ...] = ()
        if isinstance(extracted_risks, list) and all(
            isinstance(item, Mapping) for item in extracted_risks
        ):
            risks = tuple(dict(item) for item in extracted_risks)

        artifact_snapshot = TrustedArtifactSnapshot(
            tenant_id=artifact.tenant_id,
            project_id=artifact.project_id,
            document_id=artifact.document_id,
            revision_id=scope.revision_id,
            artifact_id=artifact.artifact_id,
            # A missing persisted digest is intentionally not reconstructed:
            # doing so would manufacture authority for legacy rows.
            artifact_hash=artifact.artifact_hash or "",
            trusted_artifact_payload=json.dumps(
                payload, sort_keys=True, separators=(",", ":"), default=str
            ).encode("utf-8"),
            is_trusted_active=(
                str(artifact.trust_state).lower() == "trusted"
                and str(artifact.lifecycle_status).lower() == "active"
            ),
        )
        return ReconciliationInput(
            approved_artifact=artifact_snapshot,
            v2_extracted_risks=risks,
            # See module docstring.  Do not infer revision/document scope from
            # source_artifact_id or from the selected active V2 artifact.
            historical_analyses=(),
        )


__all__ = ["SqlAlchemyHistoricalRiskAlertReconciliationReader"]
