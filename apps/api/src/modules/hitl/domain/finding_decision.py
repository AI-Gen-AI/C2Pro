"""Proposed finding-level HITL decisions (PQ-HITL-04A).

A draft decision is not a graph promotion or a workflow resume. Storage,
optimistic CAS and the *final* exact-candidate settlement remain owned by the
existing HITL / trusted-state control plane, never this domain payload.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FindingDecisionKind(StrEnum):
    RISK = "RISK"
    CRITIQUE = "CRITIQUE"


class FindingDecisionAction(StrEnum):
    CONFIRMED = "CONFIRMED"
    CORRECTION_PROPOSED = "CORRECTION_PROPOSED"
    DISMISSED = "DISMISSED"
    NEEDS_INFO = "NEEDS_INFO"


class CandidateReviewIdentity(BaseModel):
    """Immutable identity at which a human's provisional decision is directed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: UUID
    review_row_id: UUID
    document_id: UUID
    document_revision_id: UUID
    artifact_id: UUID
    artifact_version: int = Field(ge=1)
    artifact_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    generation: int = Field(ge=0)
    fencing_token: int = Field(ge=0)
    thread_id: str = Field(min_length=1)
    checkpoint_id: str = Field(min_length=1)


def stable_finding_id(
    candidate: CandidateReviewIdentity,
    kind: FindingDecisionKind,
    *,
    source_item_id: str,
    ordinal: int,
) -> str:
    """Bind one source item's identity to exactly one candidate digest.

    Display titles alone are never identity: they can be edited/duplicated.
    The source item id must come from a trusted extraction/critique envelope;
    the fingerprint does not validate the source itself.
    """
    if not source_item_id.strip() or ordinal < 0:
        raise ValueError("A nonempty source item id and nonnegative ordinal are required.")
    material = {
        "artifact_hash": candidate.artifact_hash,
        "artifact_id": str(candidate.artifact_id),
        "artifact_version": candidate.artifact_version,
        "kind": kind.value,
        "source_item_id": source_item_id,
        "ordinal": ordinal,
    }
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class FindingDecisionDraft(BaseModel):
    """Uncommitted reviewer intent; cannot itself approve an entire candidate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate: CandidateReviewIdentity
    finding_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    finding_kind: FindingDecisionKind
    action: FindingDecisionAction
    reviewer_id: str = Field(min_length=1)
    expected_ledger_revision: int = Field(ge=0)
    reason: str | None = None
    proposed_text: str | None = None

    @model_validator(mode="after")
    def validate_provisional_change(self) -> FindingDecisionDraft:
        if self.action is not FindingDecisionAction.CONFIRMED and not (
            self.reason and self.reason.strip()
        ):
            raise ValueError("Non-confirmation decisions require a reason.")
        if self.action is FindingDecisionAction.CORRECTION_PROPOSED:
            if not (self.proposed_text and self.proposed_text.strip()):
                raise ValueError("A correction needs proposed replacement text.")
        elif self.proposed_text is not None:
            raise ValueError("Only a proposed correction may carry replacement text.")
        return self
