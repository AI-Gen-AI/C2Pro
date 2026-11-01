"""S5-03: deterministic reconciliation of the human decisions taken finding by finding (owner design D1-D8, "C+B").

PURE: no I/O, no clock, no randomness. Given the exact candidate, the COMPLETE decision ledger of its review and the
typed critique observations, it says -- and digests -- what those decisions mean for the candidate:

* CONFIRMED  -> the finding is RETAINED, with the decision that confirmed it as its evidence;
* DISMISSED  -> the finding is EXCLUDED from the effective canonical content (its history is kept) and the content
  that would be signed is a DERIVED candidate (Vn+1), which this module only announces;
* NEEDS_INFO -> BLOCKS the signature until a LATER decision on that finding supersedes it;
* CORRECTION_PROPOSED -> a change that needs a NEW candidate; it is announced, never applied here;
* no decision -> the finding is UNDECIDED and blocks the signature (fail closed);
* CRITIQUE -> blocks only when it is MATERIAL, its evidence is VERIFIED and it is still OPEN; a material critique
  without verified evidence, and a non-material one, are advisories (no indiscriminate blocking). Today critique
  has no typed persisted envelope, so ``critique_coverage`` says what could (not) be evaluated -- never silently "none".

THIS IS NOT A SIGNATURE. The result neither approves, rejects, trusts nor promotes anything, holds no authority and is
not read by the final approval yet (S5-04 consumes it; S5-05 revalidates it, and the grant, inside the transaction that
commits the first TRUSTED). It only fixes WHAT a signature would be signing, as a digest that changes if ANY input does.

Latest decision on a finding wins (the ledger is append-only and ordered by ``ledger_revision``).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from src.modules.hitl.domain.finding_decision import CandidateReviewIdentity, FindingDecisionAction

RECONCILIATION_POLICY_VERSION = "s5-03/v1"


class ReconciliationStatus(StrEnum):
    CONSISTENT = "CONSISTENT"
    INCONSISTENT = "INCONSISTENT"  # the ledger / candidate cannot be trusted as input: nothing is concluded


class FindingResolution(StrEnum):
    RETAINED = "RETAINED"
    EXCLUDED = "EXCLUDED"
    BLOCKED_NEEDS_INFO = "BLOCKED_NEEDS_INFO"
    CORRECTION_PENDING = "CORRECTION_PENDING"
    UNDECIDED = "UNDECIDED"


class BlockerCode(StrEnum):
    NEEDS_INFO = "NEEDS_INFO"
    UNDECIDED_FINDING = "UNDECIDED_FINDING"
    MATERIAL_CRITIQUE_UNRESOLVED = "MATERIAL_CRITIQUE_UNRESOLVED"


class DerivationCode(StrEnum):
    """The content to sign is NOT this candidate as it stands: a new candidate (Vn+1) must be produced first."""

    DISMISSED_EXCLUSION = "DISMISSED_EXCLUSION"
    CORRECTION_PROPOSED = "CORRECTION_PROPOSED"


class AdvisoryCode(StrEnum):
    STALE_DECISIONS_IGNORED = "STALE_DECISIONS_IGNORED"
    MATERIAL_CRITIQUE_WITHOUT_VERIFIED_EVIDENCE = "MATERIAL_CRITIQUE_WITHOUT_VERIFIED_EVIDENCE"
    NON_MATERIAL_CRITIQUE = "NON_MATERIAL_CRITIQUE"
    CRITIQUE_NOT_EVALUABLE = "CRITIQUE_NOT_EVALUABLE"


class CritiqueMateriality(StrEnum):
    MATERIAL = "MATERIAL"
    NON_MATERIAL = "NON_MATERIAL"


class CritiqueEvidence(StrEnum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"


class CritiqueStatus(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class CritiqueCoverage(StrEnum):
    TYPED_OBSERVATIONS = "TYPED_OBSERVATIONS"  # a typed envelope was supplied and evaluated
    NONE_PRESENT = "NONE_PRESENT"  # the candidate has no critique at all
    UNSTRUCTURED_NOT_EVALUATED = "UNSTRUCTURED_NOT_EVALUATED"  # prose exists but has no typed materiality / evidence


@dataclass(frozen=True)
class CandidateFinding:
    ordinal: int
    source_item_id: str
    finding_id: str


@dataclass(frozen=True)
class LedgerEvent:
    """One row of ``hitl_finding_decisions``, with the identity it was recorded against."""

    event_id: UUID
    ledger_revision: int
    expected_ledger_revision: int
    finding_id: str
    finding_kind: str
    action: FindingDecisionAction
    reviewer_id: str
    reason: str | None
    proposed_text: str | None
    recorded_at: datetime | None
    tenant_id: UUID
    review_row_id: UUID
    document_id: UUID
    document_revision_id: UUID
    artifact_id: UUID
    artifact_version: int
    artifact_hash: str
    generation: int
    fencing_token: int


@dataclass(frozen=True)
class CritiqueObservation:
    observation_id: str
    materiality: CritiqueMateriality
    evidence: CritiqueEvidence
    status: CritiqueStatus
    summary: str = ""


@dataclass(frozen=True)
class ReconciliationInput:
    identity: CandidateReviewIdentity
    project_id: UUID
    findings: Sequence[CandidateFinding]
    ledger: Sequence[LedgerEvent]  # EVERY row of the review (any candidate it ever gated), in any order
    critiques: Sequence[CritiqueObservation] = ()
    critique_coverage: CritiqueCoverage = CritiqueCoverage.NONE_PRESENT


@dataclass(frozen=True)
class DecisionEvidence:
    event_id: UUID
    ledger_revision: int
    action: FindingDecisionAction
    reviewer_id: str
    reason: str | None


@dataclass(frozen=True)
class FindingOutcome:
    ordinal: int
    source_item_id: str
    finding_id: str
    resolution: FindingResolution
    decisive: DecisionEvidence | None  # the latest decision (None = UNDECIDED)
    history: tuple[DecisionEvidence, ...]  # every decision on this finding for this candidate, in order, never lost
    proposed_text_sha256: str | None = None


@dataclass(frozen=True)
class Blocker:
    code: BlockerCode
    finding_id: str | None
    detail: str


@dataclass(frozen=True)
class Derivation:
    code: DerivationCode
    finding_id: str
    detail: str


@dataclass(frozen=True)
class Advisory:
    code: AdvisoryCode
    detail: str


@dataclass(frozen=True)
class ReconciliationReceipt:
    """What S5-04 signs against and S5-05 re-validates. Equal digests mean the same candidate, ledger and critiques."""

    digest: str
    policy_version: str
    review_row_id: UUID
    project_id: UUID
    artifact_id: UUID
    artifact_version: int
    artifact_hash: str
    generation: int
    fencing_token: int
    ledger_revision: int
    signable_as_is: bool
    effective_content_digest: str


@dataclass(frozen=True)
class ReconciliationResult:
    status: ReconciliationStatus
    policy_version: str
    identity: CandidateReviewIdentity
    project_id: UUID
    ledger_revision: int  # head of the WHOLE ledger of the review (0 = empty)
    outcomes: tuple[FindingOutcome, ...]
    retained: tuple[CandidateFinding, ...]  # the effective canonical content of THIS candidate (confirmed findings)
    excluded: tuple[CandidateFinding, ...]
    blockers: tuple[Blocker, ...]
    derivations: tuple[Derivation, ...]
    advisories: tuple[Advisory, ...]
    inconsistencies: tuple[str, ...]
    stale_event_ids: tuple[UUID, ...]  # decisions taken on another candidate / generation of the same review
    critique_coverage: CritiqueCoverage
    effective_content_digest: str
    digest: str

    @property
    def signable_as_is(self) -> bool:
        """True only if NOTHING blocks and NOTHING requires a derived candidate. It is not a permission to sign."""
        return self.status is ReconciliationStatus.CONSISTENT and not self.blockers and not self.derivations

    def receipt(self) -> ReconciliationReceipt:
        return ReconciliationReceipt(
            digest=self.digest,
            policy_version=self.policy_version,
            review_row_id=self.identity.review_row_id,
            project_id=self.project_id,
            artifact_id=self.identity.artifact_id,
            artifact_version=self.identity.artifact_version,
            artifact_hash=self.identity.artifact_hash,
            generation=self.identity.generation,
            fencing_token=self.identity.fencing_token,
            ledger_revision=self.ledger_revision,
            signable_as_is=self.signable_as_is,
            effective_content_digest=self.effective_content_digest,
        )


def _canonical(material: Any) -> str:
    return json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _sha(material: Any) -> str:
    return hashlib.sha256(_canonical(material).encode("utf-8")).hexdigest()


def _identity_matches(event: LedgerEvent, identity: CandidateReviewIdentity) -> bool:
    return (
        event.document_id == identity.document_id
        and event.document_revision_id == identity.document_revision_id
        and event.artifact_id == identity.artifact_id
        and event.artifact_version == identity.artifact_version
        and event.artifact_hash == identity.artifact_hash
        and event.generation == identity.generation
        and event.fencing_token == identity.fencing_token
    )


def _ledger_inconsistencies(identity: CandidateReviewIdentity, ordered: Sequence[LedgerEvent]) -> list[str]:
    problems: list[str] = []
    revisions = [e.ledger_revision for e in ordered]
    if len(set(revisions)) != len(revisions):
        problems.append("LEDGER_DUPLICATE_REVISION")
    if revisions != list(range(1, len(ordered) + 1)):
        problems.append("LEDGER_REVISIONS_NOT_CONTIGUOUS_FROM_1")
    if len({e.event_id for e in ordered}) != len(ordered):
        problems.append("LEDGER_DUPLICATE_EVENT_ID")
    for event in ordered:
        if event.tenant_id != identity.tenant_id or event.review_row_id != identity.review_row_id:
            problems.append(f"LEDGER_EVENT_OF_ANOTHER_TENANT_OR_REVIEW:{event.event_id}")
        if event.expected_ledger_revision != event.ledger_revision - 1:
            problems.append(f"LEDGER_CAS_CHAIN_BROKEN_AT:{event.ledger_revision}")
    return problems


def _evidence(event: LedgerEvent) -> DecisionEvidence:
    return DecisionEvidence(event.event_id, event.ledger_revision, event.action, event.reviewer_id, event.reason)


_RESOLUTION_OF = {
    FindingDecisionAction.CONFIRMED: FindingResolution.RETAINED,
    FindingDecisionAction.DISMISSED: FindingResolution.EXCLUDED,
    FindingDecisionAction.NEEDS_INFO: FindingResolution.BLOCKED_NEEDS_INFO,
    FindingDecisionAction.CORRECTION_PROPOSED: FindingResolution.CORRECTION_PENDING,
}


def reconcile(data: ReconciliationInput) -> ReconciliationResult:
    """Pure and total: the same input always yields the same result and digest, whatever the order of ``ledger``."""
    identity = data.identity
    ordered = sorted(data.ledger, key=lambda e: (e.ledger_revision, str(e.event_id)))
    findings = tuple(sorted(data.findings, key=lambda f: f.ordinal))
    head = max((e.ledger_revision for e in ordered), default=0)

    inconsistencies = _ledger_inconsistencies(identity, ordered)
    if len({f.finding_id for f in findings}) != len(findings) or len({f.ordinal for f in findings}) != len(findings):
        inconsistencies.append("CANDIDATE_DUPLICATE_FINDING")

    current = [e for e in ordered if _identity_matches(e, identity)]
    stale = [e for e in ordered if not _identity_matches(e, identity)]
    known = {f.finding_id for f in findings}
    for event in current:
        if event.finding_id not in known or event.finding_kind != "RISK":
            inconsistencies.append(f"DECISION_ON_A_FINDING_OUTSIDE_THE_CANDIDATE:{event.event_id}")

    critiques = tuple(sorted(data.critiques, key=lambda c: c.observation_id))
    inconsistencies = sorted(set(inconsistencies))

    outcomes: list[FindingOutcome] = []
    blockers: list[Blocker] = []
    derivations: list[Derivation] = []
    advisories: list[Advisory] = []
    retained: list[CandidateFinding] = []
    excluded: list[CandidateFinding] = []

    if not inconsistencies:
        by_finding: dict[str, list[LedgerEvent]] = {}
        for event in current:
            by_finding.setdefault(event.finding_id, []).append(event)
        for finding in findings:
            events = by_finding.get(finding.finding_id, [])
            history = tuple(_evidence(e) for e in events)
            if not events:
                outcomes.append(FindingOutcome(finding.ordinal, finding.source_item_id, finding.finding_id, FindingResolution.UNDECIDED, None, ()))
                blockers.append(Blocker(BlockerCode.UNDECIDED_FINDING, finding.finding_id, "no human decision on this finding"))
                continue
            latest = events[-1]
            resolution = _RESOLUTION_OF[latest.action]
            text_sha = (
                hashlib.sha256((latest.proposed_text or "").encode("utf-8")).hexdigest()
                if latest.action is FindingDecisionAction.CORRECTION_PROPOSED
                else None
            )
            outcomes.append(FindingOutcome(finding.ordinal, finding.source_item_id, finding.finding_id, resolution, _evidence(latest), history, text_sha))
            if resolution is FindingResolution.RETAINED:
                retained.append(finding)
            elif resolution is FindingResolution.EXCLUDED:
                excluded.append(finding)
                derivations.append(Derivation(DerivationCode.DISMISSED_EXCLUSION, finding.finding_id, "excluded from the effective content; a derived candidate is required"))
            elif resolution is FindingResolution.BLOCKED_NEEDS_INFO:
                blockers.append(Blocker(BlockerCode.NEEDS_INFO, finding.finding_id, "needs information; unresolved until a later decision supersedes it"))
            else:
                derivations.append(Derivation(DerivationCode.CORRECTION_PROPOSED, finding.finding_id, "a correction needs a NEW candidate and its own exact signature; it was NOT applied"))

        for critique in critiques:
            if critique.materiality is CritiqueMateriality.MATERIAL and critique.status is CritiqueStatus.OPEN:
                if critique.evidence is CritiqueEvidence.VERIFIED:
                    blockers.append(Blocker(BlockerCode.MATERIAL_CRITIQUE_UNRESOLVED, None, f"{critique.observation_id}: material, verified and unresolved"))
                else:
                    advisories.append(Advisory(AdvisoryCode.MATERIAL_CRITIQUE_WITHOUT_VERIFIED_EVIDENCE, critique.observation_id))
            elif critique.materiality is CritiqueMateriality.NON_MATERIAL and critique.status is CritiqueStatus.OPEN:
                advisories.append(Advisory(AdvisoryCode.NON_MATERIAL_CRITIQUE, critique.observation_id))
        if data.critique_coverage is CritiqueCoverage.UNSTRUCTURED_NOT_EVALUATED:
            advisories.append(Advisory(AdvisoryCode.CRITIQUE_NOT_EVALUABLE, "critique prose exists but has no typed materiality / evidence"))
        if stale:
            advisories.append(Advisory(AdvisoryCode.STALE_DECISIONS_IGNORED, f"{len(stale)} decision(s) were taken on another candidate or generation of this review"))

    effective_content_digest = _sha([[f.ordinal, f.source_item_id] for f in retained])
    material = {
        "policy": RECONCILIATION_POLICY_VERSION,
        "identity": {
            "tenant_id": str(identity.tenant_id),
            "project_id": str(data.project_id),
            "review_row_id": str(identity.review_row_id),
            "document_id": str(identity.document_id),
            "document_revision_id": str(identity.document_revision_id),
            "artifact_id": str(identity.artifact_id),
            "artifact_version": identity.artifact_version,
            "artifact_hash": identity.artifact_hash,
            "generation": identity.generation,
            "fencing_token": identity.fencing_token,
        },
        "candidate_findings": [[f.ordinal, f.source_item_id, f.finding_id] for f in findings],
        "ledger_head": head,
        "ledger": [[e.ledger_revision, str(e.event_id), e.finding_id, e.action.value, e.reviewer_id, e.artifact_hash, e.generation, e.fencing_token] for e in ordered],
        "outcomes": [[o.finding_id, o.resolution.value, str(o.decisive.event_id) if o.decisive else None, o.proposed_text_sha256] for o in outcomes],
        "blockers": sorted([b.code.value, b.finding_id or "", b.detail] for b in blockers),
        "derivations": sorted([d.code.value, d.finding_id] for d in derivations),
        "advisories": sorted([a.code.value, a.detail] for a in advisories),
        "critiques": [[c.observation_id, c.materiality.value, c.evidence.value, c.status.value] for c in critiques],
        "critique_coverage": data.critique_coverage.value,
        "inconsistencies": inconsistencies,
        "effective_content_digest": effective_content_digest,
    }
    return ReconciliationResult(
        status=ReconciliationStatus.INCONSISTENT if inconsistencies else ReconciliationStatus.CONSISTENT,
        policy_version=RECONCILIATION_POLICY_VERSION,
        identity=identity,
        project_id=data.project_id,
        ledger_revision=head,
        outcomes=tuple(outcomes),
        retained=tuple(retained),
        excluded=tuple(excluded),
        blockers=tuple(blockers),
        derivations=tuple(derivations),
        advisories=tuple(advisories),
        inconsistencies=tuple(inconsistencies),
        stale_event_ids=tuple(e.event_id for e in stale),
        critique_coverage=data.critique_coverage,
        effective_content_digest=effective_content_digest,
        digest=_sha(material),
    )


def events_from_rows(rows: Iterable[Mapping[str, Any]]) -> tuple[LedgerEvent, ...]:
    """Build ``LedgerEvent`` from ledger rows (mappings keyed by the table's column names)."""
    return tuple(
        LedgerEvent(
            event_id=r["event_id"],
            ledger_revision=int(r["ledger_revision"]),
            expected_ledger_revision=int(r["expected_ledger_revision"]),
            finding_id=str(r["finding_id"]),
            finding_kind=str(r["finding_kind"]),
            action=FindingDecisionAction(str(r["action"])),
            reviewer_id=str(r["reviewer_id"]),
            reason=r["reason"],
            proposed_text=r["proposed_text"],
            recorded_at=r.get("recorded_at"),
            tenant_id=r["tenant_id"],
            review_row_id=r["review_row_id"],
            document_id=r["document_id"],
            document_revision_id=r["document_revision_id"],
            artifact_id=r["artifact_id"],
            artifact_version=int(r["artifact_version"]),
            artifact_hash=str(r["artifact_hash"]),
            generation=int(r["generation"]),
            fencing_token=int(r["fencing_token"]),
        )
        for r in rows
    )
