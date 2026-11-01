"""S5: what a human reviewer sees to decide FINDING BY FINDING (read model, no write).

For one pending review row of the signed-in tenant it reconstructs, from the authoritative rows only:

* the exact PROPOSED candidate the review gates (artifact id / version / hash, document revision, processing
  generation and fencing token) -- the pins a decision must echo back (optimistic concurrency, never authority);
* every RISK of that candidate, with the stable ``source_item_id`` and ordinal the writer verifies membership against;
* the append-only ledger of provisional decisions already taken on them, and its current revision.

A decision recorded here is PROVISIONAL reviewer intent. It does not approve, reject or trust the candidate and it is
not read by the final approval: that remains a separate act through the review route.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.domain.trust import artifact_digest
from src.modules.hitl.application.finding_review_authorization import authorize_finding_reviewer
from src.modules.hitl.domain.finding_decision import (
    CandidateReviewIdentity,
    FindingDecisionKind,
    stable_finding_id,
)
from src.modules.hitl.domain.finding_source_membership import risk_source_item_id


class ReviewFindingsUnavailable(LookupError):
    """No actionable, candidate-bound review of this tenant (unknown, foreign, closed or superseded)."""


_REVIEW = text("""
SELECT id, project_id, document_id, thread_id, checkpoint_id,
       lineage_generation, lineage_fencing_token, review_metadata
FROM public.review_items
WHERE id = cast(:review_row_id as uuid)
  AND tenant_id = cast(:tenant_id as uuid)
  AND current_status::text IN
      ('PENDING_REVIEW_REQUIRED','PENDING_REVIEW_CONDITIONAL','ESCALATED')
""")

_CANDIDATE = text("""
SELECT a.document_revision_id, a.payload, o.generation, o.fencing_token
FROM public.document_artifacts a
JOIN public.document_processing_operations o
  ON o.document_id = a.document_id AND o.tenant_id = a.tenant_id
WHERE a.artifact_id = cast(:artifact_id as uuid)
  AND a.tenant_id = cast(:tenant_id as uuid)
  AND a.project_id = cast(:project_id as uuid)
  AND a.document_id = cast(:document_id as uuid)
  AND a.artifact_version = :artifact_version
  AND a.artifact_hash = :artifact_hash
  AND a.trust_state = 'proposed'
  AND o.revision_id = a.document_revision_id
  AND o.stage = 'ANALYSIS'
""")

_LEDGER = text("""
SELECT event_id, ledger_revision, finding_id, action, reason, proposed_text, reviewer_id, recorded_at
FROM public.hitl_finding_decisions
WHERE tenant_id = cast(:tenant_id as uuid)
  AND review_row_id = cast(:review_row_id as uuid)
ORDER BY ledger_revision
""")

_RISK_FIELDS = ("title", "description", "category", "severity", "likelihood", "clause_ref")


@dataclass(frozen=True)
class FindingDecisionRecord:
    event_id: UUID
    ledger_revision: int
    action: str
    reason: str | None
    proposed_text: str | None
    reviewer_id: str
    recorded_at: datetime | None


@dataclass(frozen=True)
class ReviewFinding:
    ordinal: int
    source_item_id: str
    finding_id: str
    risk: dict[str, Any]
    current: FindingDecisionRecord | None
    history: list[FindingDecisionRecord] = field(default_factory=list)


@dataclass(frozen=True)
class ReviewFindingsView:
    review_row_id: UUID
    artifact_id: UUID
    artifact_version: int
    artifact_hash: str
    document_revision_id: UUID
    generation: int
    fencing_token: int
    ledger_revision: int
    findings: list[ReviewFinding]


def _project(risk: dict[str, Any]) -> dict[str, Any]:
    """Only the reviewer-facing fields of a risk (never the raw model payload)."""
    out: dict[str, Any] = {}
    for key in _RISK_FIELDS:
        value = risk.get(key)
        if isinstance(value, str | int | float) and not isinstance(value, bool):
            out[key] = value
        elif value is not None and hasattr(value, "value"):
            out[key] = str(value.value)
    return out


class ReviewFindingsViewService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, *, tenant_id: UUID, user: object, review_row_id: UUID) -> ReviewFindingsView:
        actor = authorize_finding_reviewer(user, tenant_id=tenant_id)
        params = {"tenant_id": actor.tenant_id, "review_row_id": review_row_id}
        review = (await self._session.execute(_REVIEW, params)).mappings().first()
        if review is None:
            raise ReviewFindingsUnavailable("no actionable review for tenant")

        metadata = review.get("review_metadata")
        bound = metadata.get("candidate_binding") if isinstance(metadata, dict) else None
        if not (
            isinstance(metadata, dict)
            and metadata.get("trust_candidate_required") is True
            and metadata.get("trust_kind") != "structured_source"
            and isinstance(bound, dict)
            and bound.get("document_id") == str(review["document_id"])
            and review["project_id"] is not None
        ):
            raise ReviewFindingsUnavailable("review is not bound to an analysis candidate")

        try:
            artifact_id = UUID(str(bound.get("artifact_id")))
            artifact_version = int(str(bound.get("artifact_version")))
        except (TypeError, ValueError) as exc:
            raise ReviewFindingsUnavailable("review candidate pin is malformed") from exc
        artifact_hash = str(bound.get("artifact_hash") or "")

        candidate_row = (
            await self._session.execute(
                _CANDIDATE,
                {
                    "artifact_id": artifact_id,
                    "tenant_id": actor.tenant_id,
                    "project_id": review["project_id"],
                    "document_id": review["document_id"],
                    "artifact_version": artifact_version,
                    "artifact_hash": artifact_hash,
                },
            )
        ).mappings().first()
        payload = candidate_row.get("payload") if candidate_row is not None else None
        if (
            candidate_row is None
            or not isinstance(payload, dict)
            or artifact_digest(payload) != artifact_hash
            or candidate_row["generation"] != review["lineage_generation"]
            or candidate_row["fencing_token"] != review["lineage_fencing_token"]
            or not review["thread_id"]
            or not review["checkpoint_id"]
        ):
            raise ReviewFindingsUnavailable("the candidate is missing, changed or superseded")

        identity = CandidateReviewIdentity(
            tenant_id=actor.tenant_id,
            review_row_id=review_row_id,
            document_id=review["document_id"],
            document_revision_id=candidate_row["document_revision_id"],
            artifact_id=artifact_id,
            artifact_version=artifact_version,
            artifact_hash=artifact_hash,
            generation=review["lineage_generation"],
            fencing_token=review["lineage_fencing_token"],
            thread_id=str(review["thread_id"]),
            checkpoint_id=str(review["checkpoint_id"]),
        )

        events = (await self._session.execute(_LEDGER, params)).mappings().all()
        by_finding: dict[str, list[FindingDecisionRecord]] = {}
        for event in events:
            by_finding.setdefault(str(event["finding_id"]), []).append(
                FindingDecisionRecord(
                    event_id=event["event_id"],
                    ledger_revision=int(event["ledger_revision"]),
                    action=str(event["action"]),
                    reason=event["reason"],
                    proposed_text=event["proposed_text"],
                    reviewer_id=str(event["reviewer_id"]),
                    recorded_at=event["recorded_at"],
                )
            )

        risks = payload.get("extracted_risks")
        findings: list[ReviewFinding] = []
        for ordinal, risk in enumerate(risks if isinstance(risks, list) else []):
            if not isinstance(risk, dict) or not risk:
                continue
            source_item_id = risk_source_item_id(risk)
            finding_id = stable_finding_id(
                identity, FindingDecisionKind.RISK, source_item_id=source_item_id, ordinal=ordinal
            )
            history = by_finding.get(finding_id, [])
            findings.append(
                ReviewFinding(
                    ordinal=ordinal,
                    source_item_id=source_item_id,
                    finding_id=finding_id,
                    risk=_project(risk),
                    current=history[-1] if history else None,
                    history=history,
                )
            )

        return ReviewFindingsView(
            review_row_id=review_row_id,
            artifact_id=artifact_id,
            artifact_version=artifact_version,
            artifact_hash=artifact_hash,
            document_revision_id=identity.document_revision_id,
            generation=identity.generation,
            fencing_token=identity.fencing_token,
            ledger_revision=max((int(e["ledger_revision"]) for e in events), default=0),
            findings=findings,
        )
