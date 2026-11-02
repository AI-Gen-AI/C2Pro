"""S5 Vn+1: produce the DERIVED candidate that DISMISSED / CORRECTION_PROPOSED decisions call for.

This is the producer the S5-03 reconciliation announces (``derivations``) and S5-04 refuses to sign without. It reuses,
and does not redesign, what already exists:

* the reconciliation (``FindingReconciliationService``) decides WHAT each decision means and digests it;
* the product's governed ``propose_correction`` is the ONLY thing that creates the new candidate: Vn is SUPERSEDED (it can
  never be committed afterwards), Vn+1 is inserted PROPOSED with the next version, and the review row rebinds to it,
  compare-and-set from the exact candidate it replaces;
* the content is decided by the pure ``domain.derived_candidate`` (exclusions and, once ratified, corrections).

What this does NOT do, on purpose: approve, reject, trust or promote anything; carry a decision over to Vn+1 (every finding
of Vn+1 is undecided and a human must decide it again); touch a TRUSTED artifact; create a resume operation, event or
analysis. Promotion remains the separate, explicit act it always was, under S5-04 (a CURRENT reconciliation of Vn+1) and
S5-05 (grant + digest revalidated inside the first-TRUSTED transaction).

Authority: ``REVIEW_FINDING`` on the review's own project (the capability to take the decisions this materializes). The
derivation only PROPOSES; a stricter rule (``APPROVE_CANDIDATE``) is a one-line change if the owner prefers it.

One transaction, one review-row lock: the review row is taken ``FOR UPDATE`` (the ledger writer's lock), so a concurrent
decision or a second derivation waits and then sees the result. The caller commits; any failure rolls back the new
candidate, the rebinding and the provenance together.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.document_artifact_repository import (
    SqlAlchemyDocumentArtifactRepository,
)
from src.analysis.domain.contracts import DocumentArtifact
from src.analysis.domain.trust import CandidateBinding, StaleCandidateError
from src.core.tenants.types import TenantId
from src.modules.hitl.application.finding_reconciliation_service import (
    _LEDGER,
    FindingReconciliationService,
)
from src.modules.hitl.application.finding_review_authorization import authorize_finding_reviewer
from src.modules.hitl.application.project_review_authorization import (
    ProjectCapability,
    ProjectReviewAuthorizer,
)
from src.modules.hitl.application.review_findings_view import _REVIEW, ReviewFindingsUnavailable
from src.modules.hitl.domain import derived_candidate as dc
from src.modules.hitl.domain.finding_reconciliation import ReconciliationStatus, events_from_rows

METADATA_KEY = "candidate_derivations"

_SOURCE = text("""
SELECT payload, document_revision_id
FROM public.document_artifacts
WHERE artifact_id = cast(:artifact_id as uuid) AND tenant_id = cast(:tenant_id as uuid)
  AND trust_state = 'proposed'
""")

_APPEND_PROVENANCE = text("""
UPDATE public.review_items
   SET review_metadata = review_metadata || jsonb_build_object(
         cast(:key as text),
         coalesce(review_metadata -> cast(:key as text), '[]'::jsonb) || cast(:entry as jsonb))
 WHERE id = cast(:review_row_id as uuid)
   AND tenant_id = cast(:tenant_id as uuid)
   AND review_metadata -> 'candidate_binding' ->> 'artifact_id' = :derived_artifact_id
RETURNING id
""")


class DerivationRefused(RuntimeError):
    """Nothing was derived. ``code`` is the stable machine-readable reason (HTTP 409)."""

    code = "derivation_refused"

    def __init__(self, message: str, *, blockers: tuple[str, ...] = (), derivations: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.blockers = blockers
        self.derivations = derivations


class DerivationBlocked(DerivationRefused):
    code = "derivation_blocked"


class NoDerivationRequired(DerivationRefused):
    code = "no_derivation_required"


class CorrectionSemanticsNotRatified(DerivationRefused):
    code = "correction_semantics_not_ratified"


class DerivationLedgerStale(DerivationRefused):
    code = "stale_ledger_revision"


class DerivationCandidateStale(DerivationRefused):
    code = "stale_or_unbound_candidate"


class DerivationNotPossible(DerivationRefused):
    code = "derivation_not_possible"


@dataclass(frozen=True)
class DerivedCandidateOutcome:
    review_row_id: UUID
    source_artifact_id: UUID
    source_artifact_version: int
    source_artifact_hash: str
    derived_artifact_id: UUID
    derived_artifact_version: int
    derived_artifact_hash: str
    reconciliation_digest: str
    source_ledger_revision: int
    retained: int
    excluded: int
    corrected: int
    replayed: bool


def _outcome_from_entry(review_row_id: UUID, entry: dict[str, Any], *, replayed: bool) -> DerivedCandidateOutcome:
    return DerivedCandidateOutcome(
        review_row_id=review_row_id,
        source_artifact_id=UUID(entry["source_artifact_id"]),
        source_artifact_version=int(entry["source_artifact_version"]),
        source_artifact_hash=str(entry["source_artifact_hash"]),
        derived_artifact_id=UUID(entry["derived_artifact_id"]),
        derived_artifact_version=int(entry["derived_artifact_version"]),
        derived_artifact_hash=str(entry["derived_artifact_hash"]),
        reconciliation_digest=str(entry["reconciliation_digest"]),
        source_ledger_revision=int(entry["source_ledger_revision"]),
        retained=len(entry.get("retained") or []),
        excluded=len(entry.get("excluded") or []),
        corrected=len(entry.get("corrected") or []),
        replayed=replayed,
    )


class DerivedCandidateService:
    def __init__(self, session: AsyncSession, authorizer: ProjectReviewAuthorizer | None = None) -> None:
        self._session = session
        self._authorizer = authorizer or ProjectReviewAuthorizer(session)

    async def execute(
        self,
        *,
        tenant_id: UUID,
        user: object,
        review_row_id: UUID,
        source_artifact_hash: str,
        expected_ledger_revision: int,
    ) -> DerivedCandidateOutcome:
        """Raises ``FindingReviewerNotAuthorized`` / ``ProjectAuthorizationDenied`` / ``ReviewFindingsUnavailable`` (as the
        other review routes do) or a ``DerivationRefused``. The caller commits."""
        actor = authorize_finding_reviewer(user, tenant_id=tenant_id)
        review = (
            await self._session.execute(
                text(_REVIEW.text + " FOR UPDATE"), {"tenant_id": tenant_id, "review_row_id": review_row_id}
            )
        ).mappings().first()
        if review is None:
            raise ReviewFindingsUnavailable("no actionable review for tenant")
        await self._authorizer.require(
            tenant_id=actor.tenant_id, user_id=actor.reviewer_id, project_id=review["project_id"],
            capability=ProjectCapability.REVIEW_FINDING,
        )

        raw_metadata = review.get("review_metadata")
        metadata: dict[str, Any] = raw_metadata if isinstance(raw_metadata, dict) else {}
        for entry in metadata.get(METADATA_KEY) or []:
            if entry.get("source_artifact_hash") == source_artifact_hash and entry.get("source_ledger_revision") == expected_ledger_revision:
                return _outcome_from_entry(review_row_id, entry, replayed=True)

        result = await FindingReconciliationService(self._session, self._authorizer).reconcile_for_member(
            tenant_id=actor.tenant_id, user_id=actor.reviewer_id, review_row_id=review_row_id,
            capability=ProjectCapability.REVIEW_FINDING,
        )
        identity = result.identity
        if identity.artifact_hash != source_artifact_hash:
            raise DerivationCandidateStale("the candidate in the request is not the review's current candidate")
        if result.ledger_revision != expected_ledger_revision:
            raise DerivationLedgerStale(
                f"the ledger is at revision {result.ledger_revision}, the request was built on {expected_ledger_revision}"
            )
        if result.status is not ReconciliationStatus.CONSISTENT:
            raise DerivationNotPossible(
                "the decision ledger is inconsistent; nothing is derived: " + ", ".join(result.inconsistencies)
            )
        if result.blockers:
            raise DerivationBlocked(
                "every finding must be decided and none may be waiting for information before a candidate is derived",
                blockers=tuple(b.code.value for b in result.blockers),
                derivations=tuple(d.code.value for d in result.derivations),
            )
        if not result.derivations:
            raise NoDerivationRequired("the decisions keep the candidate as it is: approve it, no derived candidate is needed")
        if dc.requires_corrections(result) and not dc.CORRECTIONS_RATIFIED:
            raise CorrectionSemanticsNotRatified(
                "a proposed correction cannot be materialized until the owner ratifies which field it replaces"
            )

        source = (
            await self._session.execute(_SOURCE, {"artifact_id": identity.artifact_id, "tenant_id": actor.tenant_id})
        ).mappings().first()
        payload = source["payload"] if source is not None else None
        if source is None or not isinstance(payload, dict) or not isinstance(payload.get("extracted_risks"), list):
            raise DerivationCandidateStale("the source candidate is missing or no longer proposed")
        ledger = events_from_rows(
            [dict(r) for r in (await self._session.execute(_LEDGER, {"tenant_id": actor.tenant_id, "review_row_id": review_row_id})).mappings().all()]
        )
        try:
            content = dc.derive_content(payload["extracted_risks"], result, ledger)
        except dc.NotDerivable as exc:
            raise DerivationNotPossible(str(exc)) from exc

        derived_payload = {**payload, "extracted_risks": list(content.risks)}
        try:
            new_binding = await SqlAlchemyDocumentArtifactRepository(self._session).propose_correction(
                CandidateBinding(
                    artifact_id=identity.artifact_id, document_id=identity.document_id,
                    artifact_version=identity.artifact_version, artifact_hash=identity.artifact_hash,
                ),
                DocumentArtifact.model_validate(derived_payload),
                tenant_id=TenantId(actor.tenant_id),
                review_row_id=review_row_id,
            )
        except StaleCandidateError as exc:
            raise DerivationCandidateStale(str(exc)) from exc

        entry = dc.provenance_entry(
            result=result, content=content, source_document_revision_id=source["document_revision_id"],
            derived_artifact_id=new_binding.artifact_id, derived_artifact_version=new_binding.artifact_version,
            derived_artifact_hash=new_binding.artifact_hash, derived_by=actor.reviewer_id,
        )
        await self._record_provenance(review_row_id, actor.tenant_id, new_binding.artifact_id, entry)
        return _outcome_from_entry(review_row_id, entry, replayed=False)

    async def _record_provenance(self, review_row_id: UUID, tenant_id: UUID, derived_artifact_id: UUID, entry: dict[str, Any]) -> None:
        recorded = (
            await self._session.execute(
                _APPEND_PROVENANCE,
                {
                    "key": METADATA_KEY, "entry": json.dumps(entry, sort_keys=True), "review_row_id": review_row_id,
                    "tenant_id": tenant_id, "derived_artifact_id": str(derived_artifact_id),
                },
            )
        ).all()
        if not recorded:
            raise DerivationCandidateStale("the review is no longer bound to the derived candidate; the derivation is rolled back")
