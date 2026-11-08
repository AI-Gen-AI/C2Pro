"""Typed ProjectGraph state for ADR-017 Tier-2 skeleton.

TS-UT-ADR017-PG-001
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Annotated, Any, NotRequired, Protocol, TypedDict
from uuid import UUID

from src.analysis.adapters.graph.project_coherence_result import ProjectCoherenceResult
from src.analysis.domain.contracts import DocumentArtifact
from src.analysis.domain.node_result import NodeResult, merge_node_results
from src.change_intelligence.domain.change_impact_report import ChangeImpactReport
from src.core.tenants.types import TenantId


class ProjectGraphArtifactRepository(Protocol):
    """Runtime dependency for Tier-2 artifact lookups."""

    async def list_superseded_for_document(
        self,
        *,
        project_id: UUID,
        tenant_id: TenantId,
        document_id: UUID,
    ) -> list[DocumentArtifact]: ...


@dataclass(frozen=True)
class CoherenceAlertEvidence:
    """Raw output of the canonical Coherence evaluation, kept for Alert reconciliation.

    ``alerts`` are the engine's own ``evaluation.alerts`` and ``source_clauses`` the
    clause list that evaluation was run with.  Alerts are never rebuilt from the
    ``ProjectCoherenceResult`` score summary.  ``artifact_revision_ids`` records the
    TRUSTED artifact revisions the evaluation was computed from.
    """

    alerts: tuple[Any, ...]
    source_clauses: tuple[Any, ...]
    score_version: str | None
    artifact_revision_ids: tuple[str, ...]


class ProjectGraphAlertCorrelationRunner(Protocol):
    """Seam that reconciles raw Coherence alerts into the Alerts ledger."""

    async def correlate(
        self,
        *,
        project_id: UUID,
        tenant_id: TenantId,
        coherence_result: ProjectCoherenceResult | dict[str, object] | None,
        evaluation_alerts: Sequence[Any],
        source_clauses: Sequence[Any],
    ) -> Mapping[str, object]: ...


class ProjectGraphSnapshotRepository(Protocol):
    async def latest(self, project_id: UUID, tenant_id: TenantId) -> Any: ...

    async def append_snapshot(self, snapshot: Any) -> Any: ...


class ProjectGraphState(TypedDict):
    """Small Tier-2 state, separate from the Tier-1 document graph state."""

    project_id: UUID
    tenant_id: TenantId
    trigger_event_id: UUID | None
    previous_snapshot_id: UUID | None
    changed_artifact_ids: list[UUID | str]
    artifacts: list[DocumentArtifact]
    # Read-only references to canonical XLSX source rows, not approved baselines
    # and not extra trusted DocumentArtifact records.
    structured_source_refs: NotRequired[list[dict[str, Any]]]
    # Canonical original XLSX rows (validated again against their unit SHA-256).
    structured_source_units: NotRequired[list[dict[str, Any]]]
    # Read-only, literal clause facts from revision-stamped DOCX source chunks.
    structured_document_quotes: NotRequired[list[dict[str, Any]]]
    # Non-scoring, provisional discrepancies with two immutable evidence pointers.
    structured_source_comparison: NotRequired[dict[str, Any]]
    coherence_result: ProjectCoherenceResult | dict[str, object] | None
    # Raw evaluation alerts + source clauses behind ``coherence_result`` (None when
    # the evaluation did not run or degraded).
    coherence_alert_evidence: NotRequired[CoherenceAlertEvidence | None]
    impact_result: ChangeImpactReport | dict[str, object] | None
    health_result: dict[str, object] | None
    snapshot_id: UUID | None
    coherence_score_version: NotRequired[str | None]
    snapshot_repository: NotRequired[ProjectGraphSnapshotRepository]
    alert_correlation_runner: NotRequired[ProjectGraphAlertCorrelationRunner]
    node_results: Annotated[list[NodeResult[object]], merge_node_results]
    artifact_repository: NotRequired[ProjectGraphArtifactRepository]


__all__ = ["CoherenceAlertEvidence", "ProjectGraphState"]
