"""``wbs-proposal/v1``: the model response envelope and the immutable stored proposal item.

The model-facing schemas are strict (unknown fields refused): they have no approver, actor,
status, submission, profile-pin, tool or change-set field, so no output -- whatever a document
says -- can carry governance. Proposals are expressed in the PC-2a command algebra minus
ADOPT_LEGACY_NODE (a human-only legacy disposition). New nodes are named by short local labels
that can never look like canonical ids; C2Pro mints real ids only when a human applies an item.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.wbs.intelligence.contracts.evidence import (
    EvidenceItem,
    ModelEvidenceCitation,
    ProfileRuleRef,
)
from src.wbs.intelligence.contracts.qualification import (
    NotEvaluatedReason,
    QualificationDimension,
    QualificationStatus,
)

PROPOSAL_CONTRACT_VERSION = "wbs-proposal/v1"
LOCAL_LABEL = r"^[a-z][a-z0-9_-]{0,31}$"  # max 32 chars: a 36-char UUID can never be a label
ITEM_REF = LOCAL_LABEL
RULE_REF = r"^[a-z][a-z0-9_]{1,40}:[a-z][a-z0-9_]{1,40}$"  # "<profile_id>:<rule_id>"


class ProposalOperation(StrEnum):
    ADD_NODE = "ADD_NODE"
    UPDATE_NODE = "UPDATE_NODE"
    RECODE_NODE = "RECODE_NODE"
    MOVE_NODE = "MOVE_NODE"
    REORDER_NODE = "REORDER_NODE"
    REMOVE_NODE = "REMOVE_NODE"
    SPLIT_NODE = "SPLIT_NODE"
    MERGE_NODES = "MERGE_NODES"


DESTRUCTIVE_OPERATIONS = frozenset({ProposalOperation.REMOVE_NODE, ProposalOperation.SPLIT_NODE,
                                    ProposalOperation.MERGE_NODES})


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TargetRef(_Strict):
    """A node of the target snapshot (``node_id``) or a node created by another item (``label``)."""

    node_id: UUID | None = None
    label: str | None = Field(default=None, pattern=LOCAL_LABEL)

    @model_validator(mode="after")
    def _exactly_one(self) -> TargetRef:
        if (self.node_id is None) == (self.label is None):
            raise ValueError("a node reference is exactly one of node_id or label")
        return self


class ModelNodeSpec(_Strict):
    name: str = Field(min_length=1, max_length=255)
    code: str | None = Field(default=None, max_length=50)
    control_level: str = "none"
    decomposition_kind: str | None = None
    dictionary: dict[str, Any] | None = None


class ModelNodeChanges(_Strict):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    control_level: str | None = None
    decomposition_kind: str | None = None
    dictionary: dict[str, Any] | None = None


class ModelSplitTarget(_Strict):
    label: str = Field(pattern=LOCAL_LABEL)
    spec: ModelNodeSpec


class ModelProposalItem(_Strict):
    """One proposed governed edit, exactly as a model may express it."""

    ref: str = Field(pattern=ITEM_REF)
    operation: ProposalOperation
    node: TargetRef | None = None  # UPDATE / RECODE / MOVE / REORDER / REMOVE / SPLIT source
    sources: tuple[TargetRef, ...] = ()  # MERGE
    parent: TargetRef | None = None  # ADD / MOVE / MERGE placement (None = top level)
    position: int | None = Field(default=None, ge=1)
    creates_label: str | None = Field(default=None, pattern=LOCAL_LABEL)  # ADD / MERGE target
    spec: ModelNodeSpec | None = None  # ADD / MERGE target
    changes: ModelNodeChanges | None = None  # UPDATE
    code: str | None = Field(default=None, max_length=50)  # RECODE
    split_targets: tuple[ModelSplitTarget, ...] = ()  # SPLIT
    child_targets: dict[str, int] = Field(default_factory=dict)  # SPLIT: child node_id -> target index
    depends_on: tuple[str, ...] = ()
    rationale: str = Field(min_length=1, max_length=2000)
    evidence: tuple[ModelEvidenceCitation, ...] = ()
    confidence_pct: int = Field(ge=0, le=100, strict=True)
    assumptions: tuple[str, ...] = ()
    ambiguity_flags: tuple[str, ...] = ()
    profile_rule_refs: tuple[str, ...] = ()
    addresses_findings: tuple[str, ...] = ()


class ModelDimensionResult(_Strict):
    dimension: QualificationDimension
    status: QualificationStatus
    summary: str = Field(min_length=1, max_length=1000)
    reason_code: NotEvaluatedReason | None = None
    evidence: tuple[ModelEvidenceCitation, ...] = ()
    confidence_pct: int | None = Field(default=None, ge=0, le=100, strict=True)
    profile_rule_refs: tuple[str, ...] = ()
    node_ids: tuple[UUID, ...] = ()


class ModelFinding(_Strict):
    ref: str = Field(pattern=ITEM_REF)
    dimension: QualificationDimension
    status: Literal["GAP", "WARNING", "AMBIGUOUS"]
    summary: str = Field(min_length=1, max_length=1000)
    node_ids: tuple[UUID, ...] = ()
    evidence: tuple[ModelEvidenceCitation, ...] = ()
    confidence_pct: int | None = Field(default=None, ge=0, le=100, strict=True)
    profile_rule_refs: tuple[str, ...] = ()


class ModelResponseEnvelope(_Strict):
    contract_version: Literal["wbs-proposal/v1"]
    outcome: Literal["COMPLETE", "PARTIAL_PROPOSAL", "INSUFFICIENT_EVIDENCE"]
    qualification: tuple[ModelDimensionResult, ...] = ()
    findings: tuple[ModelFinding, ...] = ()
    proposals: tuple[ModelProposalItem, ...] = ()
    uncovered: tuple[str, ...] = ()


class ConfidenceBand(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


def confidence_band(pct: int) -> ConfidenceBand:
    """Confidence is presentation, never authority."""
    return ConfidenceBand.HIGH if pct >= 75 else ConfidenceBand.MEDIUM if pct >= 40 else ConfidenceBand.LOW


class ProposalItem(_Strict):
    """An immutable, server-validated proposal: applying it is a human action through PC-2a."""

    item_id: UUID  # minted by C2Pro
    ref: str = Field(pattern=ITEM_REF)
    contract_version: Literal["wbs-proposal/v1"] = "wbs-proposal/v1"
    operation: ProposalOperation
    payload: dict[str, Any]  # the normalised command (snapshot ids or local labels only)
    affected_node_ids: tuple[UUID, ...]
    target_fingerprints: dict[str, str]  # node_id -> node digest at run time (stale protection)
    creates_labels: tuple[str, ...]
    uses_labels: tuple[str, ...]
    depends_on: tuple[UUID, ...]  # prerequisite item ids (explicit and through labels)
    rationale: str
    evidence: tuple[EvidenceItem, ...]
    confidence_pct: int = Field(ge=0, le=100, strict=True)
    confidence: ConfidenceBand
    assumptions: tuple[str, ...]
    ambiguity_flags: tuple[str, ...]
    profile_rule_refs: tuple[ProfileRuleRef, ...]
    addresses_finding_ids: tuple[UUID, ...]
    destructive: bool


__all__ = [
    "DESTRUCTIVE_OPERATIONS",
    "LOCAL_LABEL",
    "PROPOSAL_CONTRACT_VERSION",
    "ConfidenceBand",
    "ModelDimensionResult",
    "ModelFinding",
    "ModelNodeChanges",
    "ModelNodeSpec",
    "ModelProposalItem",
    "ModelResponseEnvelope",
    "ModelSplitTarget",
    "ProposalItem",
    "ProposalOperation",
    "TargetRef",
    "confidence_band",
]
