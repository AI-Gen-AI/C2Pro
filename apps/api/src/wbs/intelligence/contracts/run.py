"""Run identity of WBS intelligence: scope, target, outcome and the idempotency key.

Every boundary is tenant- and project-explicit (``RunScope`` has no defaults). A run binds the
exact target identity (kind, id, digest, candidate revision, base baseline). The idempotency key
binds everything that determines a result and nothing volatile: the same request may reuse a
completed run of the same tenant; any different evidence, profile, model, template or target is a
new run; a human "re-run" adds a nonce because model output is not deterministic. A DETERMINISTIC
run has no model and no prompt template: its key binds ``model: null`` and the engine version
(``orchestration_version``) instead -- model provenance is never fabricated. An AI run that executes
under configurable limits also binds its versioned ``execution_config_digest`` (different limits =
a new run); the field is absent from the key body when not given, so existing keys never move.

Run STATUS (persistence lifecycle) and run OUTCOME (the result vocabulary) are kept separate.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.wbs.domain.digest import canonical_json
from src.wbs.intelligence.contracts.proposal import PROPOSAL_CONTRACT_VERSION
from src.wbs.intelligence.contracts.qualification import QUALIFICATION_VOCAB_VERSION

IDEMPOTENCY_KEY_VERSION = "wbs-intelligence-run-key/v1"
_DIGEST = r"^sha256:[0-9a-f]{64}$"


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class IntelligenceMode(StrEnum):
    GENERATE = "GENERATE"
    IMPORT_REVIEW = "IMPORT_REVIEW"
    REVIEW_OPTIMIZE = "REVIEW_OPTIMIZE"


class TargetKind(StrEnum):
    NONE = "NONE"  # GENERATE with no structure under review
    IMPORT = "IMPORT"
    CANDIDATE = "CANDIDATE"
    BASELINE = "BASELINE"


class ExecutionType(StrEnum):
    DETERMINISTIC = "DETERMINISTIC"  # no model call, no model provenance
    AI = "AI"  # a validated model response; model provenance is mandatory


class RunStatus(StrEnum):
    REQUESTED = "REQUESTED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TERMINAL_STATUSES = frozenset({RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED})


class RunOutcome(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL_PROPOSAL = "PARTIAL_PROPOSAL"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


REUSABLE_OUTCOMES = frozenset({RunOutcome.COMPLETE, RunOutcome.PARTIAL_PROPOSAL, RunOutcome.INSUFFICIENT_EVIDENCE})


class RunScope(_Frozen):
    tenant_id: UUID
    project_id: UUID


class RunTarget(_Frozen):
    kind: TargetKind
    target_id: UUID | None = None
    digest: str | None = Field(default=None, pattern=_DIGEST)
    change_set_revision: int | None = Field(default=None, ge=1)
    base_baseline_id: UUID | None = None

    @model_validator(mode="after")
    def _exact_identity(self) -> RunTarget:
        if self.kind is TargetKind.NONE:
            if any(v is not None for v in (self.target_id, self.digest, self.change_set_revision, self.base_baseline_id)):
                raise ValueError("a run without a target carries no target identity")
            return self
        if self.target_id is None or self.digest is None:
            raise ValueError("a target is bound by its id and exact digest")
        if (self.kind is TargetKind.CANDIDATE) != (self.change_set_revision is not None):
            raise ValueError("a candidate target (and only it) is bound to its change-set revision")
        return self


class ModelFingerprint(_Frozen):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    routing_tier: str | None = None
    temperature_milli: int = Field(ge=0, le=2000)  # integers only: digests reject floats
    max_tokens: int = Field(ge=1)


class PromptTemplateRef(_Frozen):
    task: str = Field(min_length=1)
    version: str = Field(min_length=1)
    digest: str = Field(pattern=_DIGEST)


def idempotency_key(
    *,
    scope: RunScope,
    mode: IntelligenceMode,
    target: RunTarget,
    evidence_set_digest: str,
    profile_digests: Sequence[str],
    prompt_templates: Sequence[PromptTemplateRef | Mapping[str, str]] = (),
    model: ModelFingerprint | None,
    orchestration_version: str,
    proposal_contract_version: str = PROPOSAL_CONTRACT_VERSION,
    qualification_vocab_version: str = QUALIFICATION_VOCAB_VERSION,
    rerun_nonce: str | None = None,
    execution_config_digest: str | None = None,
) -> str:
    """The tenant-scoped key of one deterministic run request (no timestamps, no volatile input)."""
    templates = sorted(
        (PromptTemplateRef.model_validate(t).model_dump() for t in prompt_templates),
        key=lambda t: (t["task"], t["version"]),
    )
    body = {
        "version": IDEMPOTENCY_KEY_VERSION,
        "tenant_id": str(scope.tenant_id),
        "project_id": str(scope.project_id),
        "mode": mode.value,
        "target": target.model_dump(mode="json"),
        "evidence_set_digest": evidence_set_digest,
        "profile_digests": sorted(set(profile_digests)),
        "proposal_contract_version": proposal_contract_version,
        "qualification_vocab_version": qualification_vocab_version,
        "prompt_templates": templates,
        "model": None if model is None else model.model_dump(mode="json"),
        "orchestration_version": orchestration_version,
        "rerun_nonce": rerun_nonce,
    }
    if execution_config_digest is not None:
        body["execution_config_digest"] = execution_config_digest
    return "sha256:" + hashlib.sha256(canonical_json(body)).hexdigest()


__all__ = [
    "REUSABLE_OUTCOMES",
    "TERMINAL_STATUSES",
    "ExecutionType",
    "IntelligenceMode",
    "ModelFingerprint",
    "PromptTemplateRef",
    "RunOutcome",
    "RunScope",
    "RunStatus",
    "RunTarget",
    "TargetKind",
    "idempotency_key",
]
