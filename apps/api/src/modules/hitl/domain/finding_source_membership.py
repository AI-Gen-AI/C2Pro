"""PQ-HITL-04B3: prove a risk exists in one immutable candidate revision.

This is item membership, not proof that the AI interpretation is correct or
that a quotation exists in the original contract. Unstructured N12 critique
is deliberately unsupported until a typed source-observation contract exists.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from src.analysis.domain.contracts import DocumentArtifact
from src.analysis.domain.trust import artifact_digest
from src.modules.hitl.domain.finding_decision import (
    CandidateReviewIdentity,
    FindingDecisionKind,
)


class UnverifiedFindingSource(ValueError):
    """No uniquely bound risk in the specified immutable candidate."""


@dataclass(frozen=True)
class VerifiedFindingSource:
    finding_kind: FindingDecisionKind
    source_item_id: str
    source_ordinal: int


def resolve_finding_source(
    *,
    candidate: CandidateReviewIdentity,
    artifact: DocumentArtifact,
    kind: FindingDecisionKind,
    ordinal: int,
) -> VerifiedFindingSource:
    """Derive identity from actual typed candidate content, never display titles."""
    if (
        artifact.document_id != str(candidate.document_id)
        or artifact.document_revision_id != str(candidate.document_revision_id)
        or artifact_digest(artifact.model_dump(mode="json")) != candidate.artifact_hash
    ):
        raise UnverifiedFindingSource("candidate document, revision or digest mismatch")
    if kind is not FindingDecisionKind.RISK:
        raise UnverifiedFindingSource("unstructured critique has no verified item identity")
    if ordinal < 0 or ordinal >= len(artifact.extracted_risks):
        raise UnverifiedFindingSource("risk ordinal does not exist in candidate")
    risk = artifact.extracted_risks[ordinal]
    data = risk.model_dump(mode="json")
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return VerifiedFindingSource(
        finding_kind=kind,
        source_item_id=f"risk:{ordinal}:{digest}",
        source_ordinal=ordinal,
    )
