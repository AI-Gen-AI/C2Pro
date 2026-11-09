"""Pure, fail-closed trusted/revision-bound inputs -> canonical ProjectState.

This is a *candidate* materializer for Tier-2, NOT a DB writer or a HITL
authority. It accepts a verified trust envelope supplied by a tenant-scoped
repository, and only clause rows physically bound to that same document
revision. Unverified model risk quotes never become canonical risk entities.

The calling runtime MUST obtain bundles from the canonical TRUSTED + ACTIVE
artifact repository; constructing this input type does not confer trust.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from uuid import NAMESPACE_URL, UUID, uuid5

from src.analysis.domain.contracts import DocumentArtifact
from src.documents.domain.models import Clause as SourceClause
from src.evidence.domain.runtime_trust import EvidenceRef, EvidenceTier
from src.project_state.domain.aggregate import ProjectState
from src.project_state.domain.entities import Clause, ProjectRisk


@dataclass(frozen=True)
class TrustedRevisionBundle:
    """Snapshot from an already-authorized tenant + revision scoped repository."""

    artifact: DocumentArtifact
    source_clauses: tuple[SourceClause, ...]
    trust_state: str
    lifecycle_status: str


@dataclass(frozen=True)
class ProjectionDiagnostics:
    input_bundles: int
    revision_bound_clauses: int
    source_bound_risks: int
    rejected_unverified_risks: int
    missing_clause_source_revisions: int


@dataclass(frozen=True)
class TrustedStateCandidate:
    state: ProjectState
    diagnostics: ProjectionDiagnostics


def _as_uuid(value: str | UUID | None, *, label: str) -> UUID:
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"TRUSTED_STATE_{label.upper()}_INVALID") from exc


def build_trusted_state_candidate(
    *,
    project_id: UUID,
    tenant_id: UUID,
    bundles: Sequence[TrustedRevisionBundle],
) -> TrustedStateCandidate | None:
    """Build only evidence-backed clauses/risks, with stable entity identity.

    Reject duplicates and identity mismatches instead of choosing a revision.
    Returns None when no trusted bundle exists; no empty synthetic aggregate.
    """
    if not bundles:
        return None

    revisions: set[UUID] = set()
    documents: set[UUID] = set()
    seen_clause_ids: set[UUID] = set()
    seen_risk_ids: set[UUID] = set()
    clauses: list[Clause] = []
    risks: list[ProjectRisk] = []
    rejected_risks = 0
    missing_clause_revisions = 0

    for bundle in sorted(
        bundles, key=lambda b: (str(b.artifact.document_id), str(b.artifact.document_revision_id))
    ):
        # This is a second check, NOT a replacement for authenticated DB query.
        if bundle.trust_state != "trusted" or bundle.lifecycle_status != "active":
            raise ValueError("TRUSTED_STATE_UNTRUSTED_ARTIFACT")
        art = bundle.artifact
        doc_id = _as_uuid(art.document_id, label="document_id")
        revision = _as_uuid(art.document_revision_id, label="revision_id")
        if doc_id in documents or revision in revisions:
            raise ValueError("TRUSTED_STATE_DUPLICATE_DOCUMENT_OR_REVISION")
        documents.add(doc_id)
        revisions.add(revision)

        physical_clauses: list[SourceClause] = []
        for source_clause in bundle.source_clauses:
            if (
                source_clause.project_id != project_id
                or source_clause.tenant_id != tenant_id
                or source_clause.document_id != doc_id
            ):
                raise ValueError("TRUSTED_STATE_CROSS_TENANT_OR_DOCUMENT")
            if source_clause.revision_id is None:
                missing_clause_revisions += 1
                continue
            if source_clause.revision_id != revision:
                raise ValueError("TRUSTED_STATE_WRONG_REVISION")
            if not isinstance(source_clause.full_text, str) or not source_clause.full_text.strip():
                continue
            if source_clause.id in seen_clause_ids:
                raise ValueError("TRUSTED_STATE_DUPLICATE_PHYSICAL_CLAUSE")
            seen_clause_ids.add(source_clause.id)
            physical_clauses.append(source_clause)
            # Weak denotes source-located text, NOT independent legal approval.
            clauses.append(
                Clause(
                    entity_id=source_clause.id,
                    source_revision_id=revision,
                    clause_id=source_clause.clause_code,
                    text=source_clause.full_text,
                    char_start=source_clause.text_start_offset,
                    char_end=source_clause.text_end_offset,
                    evidence=[
                        EvidenceRef(
                            ref_id=str(source_clause.id),
                            source="trusted_revision_clause",
                            tier=EvidenceTier.WEAK,
                            locator=f"{doc_id}/{revision}/{source_clause.id}",
                        )
                    ],
                )
            )
        for risk in art.extracted_risks:
            if (
                risk.source_quote_status != "VERIFIED"
                or not isinstance(risk.source_quote, str)
                or not risk.source_quote.strip()
            ):
                rejected_risks += 1
                continue
            # Exactly one physically anchored clause; reject stitched, other
            # document/revision quotes, and ambiguous duplicate provenance.
            matching_clauses = [
                c for c in physical_clauses if risk.source_quote in (c.full_text or "")
            ]
            if len(matching_clauses) != 1:
                rejected_risks += 1
                continue
            physical_clause = matching_clauses[0]
            # Stable across extraction-list permutations; repeated identical
            # risk claims cannot gain extra identities and inflate Health.
            normalized = json.dumps(
                risk.model_dump(mode="json"),
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            digest = sha256(normalized.encode("utf-8")).hexdigest()
            key = (
                f"c2pro/canonical-risk/{tenant_id}/{project_id}/{doc_id}/"
                f"{revision}/{physical_clause.id}/{digest}"
            )
            risk_id = uuid5(NAMESPACE_URL, key)
            if risk_id in seen_risk_ids:
                raise ValueError("TRUSTED_STATE_DUPLICATE_RISK")
            seen_risk_ids.add(risk_id)
            risks.append(
                ProjectRisk(
                    entity_id=risk_id,
                    source_revision_id=revision,
                    payload=risk,
                    evidence=[
                        EvidenceRef(
                            ref_id=str(physical_clause.id),
                            source="trusted_revision_clause",
                            tier=EvidenceTier.WEAK,
                            locator=f"{doc_id}/{revision}/{physical_clause.id}",
                        )
                    ],
                )
            )

    return TrustedStateCandidate(
        state=ProjectState(
            project_id=project_id,
            tenant_id=tenant_id,
            document_revision_ids=sorted(revisions, key=str),
            clauses=sorted(clauses, key=lambda item: str(item.entity_id)),
            risks=sorted(risks, key=lambda item: str(item.entity_id)),
        ),
        diagnostics=ProjectionDiagnostics(
            input_bundles=len(bundles),
            revision_bound_clauses=len(clauses),
            source_bound_risks=len(risks),
            rejected_unverified_risks=rejected_risks,
            missing_clause_source_revisions=missing_clause_revisions,
        ),
    )


__all__ = [
    "TrustedRevisionBundle",
    "TrustedStateCandidate",
    "ProjectionDiagnostics",
    "build_trusted_state_candidate",
]
