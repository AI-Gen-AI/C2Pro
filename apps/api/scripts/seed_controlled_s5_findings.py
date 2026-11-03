"""Nonproduction ONLY: give a pending analysis review a CONTROLLED candidate with KNOWN RISK findings.

Why this exists: the deterministic provider (``C2PRO_AI_MOCK=1``) honestly extracts NO risks, so the per-finding
decision flow (S5) could not be exercised without paid AI. This script does not add a provider, a mock mode or an
authority. It uses the product's own governed operation for changing the exact candidate a review gates --
``DocumentArtifactRepository.propose_correction`` -- so that:

* Vn (the candidate the worker produced) is SUPERSEDED and can never be committed afterwards;
* Vn+1 carries the KNOWN risks below and is PROPOSED, bound (id / version / SHA-256) to the SAME pending review row,
  which keeps its thread, checkpoint and processing lineage (generation, fencing token);
* nothing is approved, rejected or trusted, and the human final approval stays a separate act.

It is NOT equivalent to a UAT with real AI: the findings are authored, not extracted. The evidence class stays
``DETERMINISTIC_CONTROLLED_CANDIDATE`` and the manifest says so.

Fails closed: it refuses to run outside ``ENVIRONMENT=test``, for a document with no pending candidate-bound analysis
review, for a candidate that already has finding decisions, or when the review is not bound to a PROPOSED analysis
artifact.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.document_artifact_repository import (
    SqlAlchemyDocumentArtifactRepository,
)
from src.analysis.adapters.persistence.models import DocumentArtifactORM
from src.analysis.domain.contracts import DocumentArtifact, RiskItem, Severity
from src.analysis.domain.trust import CandidateBinding, TrustState
from src.core.database import close_db, get_session_with_tenant, init_db
from src.core.tenants.types import TenantId

EVIDENCE_CLASS = "DETERMINISTIC_CONTROLLED_CANDIDATE"

# Five realistic construction-contract risks, authored (not extracted). Their order is their ordinal.
CONTROLLED_RISKS: tuple[dict[str, Any], ...] = (
    {
        "title": "Late completion penalty",
        "description": "Liquidated damages of 0.1% of the contract price per day apply after 30/06/2027.",
        "category": "TIME",
        "severity": Severity.HIGH,
        "clause_ref": "Clause 14.2",
        "confidence": 0.92,
    },
    {
        "title": "Price revision after approval",
        "description": "The contractor may revise unit prices once the design is approved, without a cap.",
        "category": "BUDGET",
        "severity": Severity.MEDIUM,
        "clause_ref": "Clause 9.4",
        "confidence": 0.81,
    },
    {
        "title": "Unlimited warranty liability",
        "description": "Warranty liability is not capped and survives final acceptance for ten years.",
        "category": "LEGAL",
        "severity": Severity.CRITICAL,
        "clause_ref": "Clause 21.1",
        "confidence": 0.88,
    },
    {
        "title": "Subcontractor approval silence",
        "description": "The owner's silence for 30 days is deemed approval of a proposed subcontractor.",
        "category": "LEGAL",
        "severity": Severity.MEDIUM,
        "clause_ref": "Clause 6.3",
        "confidence": 0.64,
    },
    {
        "title": "Site access not guaranteed",
        "description": "Access to the site is promised 'as soon as practicable' with no date.",
        "category": "TIME",
        "severity": Severity.LOW,
        "clause_ref": "Clause 4.1",
        "confidence": 0.57,
    },
)

_PENDING_REVIEW = text("""
SELECT id, review_metadata
FROM public.review_items
WHERE tenant_id = cast(:tenant_id as uuid)
  AND document_id = cast(:document_id as uuid)
  AND current_status::text IN ('PENDING_REVIEW_REQUIRED','PENDING_REVIEW_CONDITIONAL','ESCALATED')
  AND review_metadata ? 'candidate_binding'
ORDER BY created_at DESC
""")

_LEDGER_EXISTS = text(
    "SELECT to_regclass('public.hitl_finding_decisions') IS NOT NULL AS present"
)
_LEDGER_ROWS = text(
    "SELECT count(*) FROM public.hitl_finding_decisions WHERE tenant_id = cast(:t as uuid) AND review_row_id = cast(:r as uuid)"
)


class ControlledSeedError(RuntimeError):
    """A precondition of the controlled candidate could not be established."""


def controlled_risks() -> list[RiskItem]:
    return [RiskItem(**risk) for risk in CONTROLLED_RISKS]


async def seed_controlled_findings(
    session: AsyncSession, *, tenant_id: UUID, document_id: UUID
) -> dict[str, Any]:
    """Replace the pending candidate of ``document_id`` by one carrying the known risks (caller commits)."""
    rows = (
        await session.execute(_PENDING_REVIEW, {"tenant_id": tenant_id, "document_id": document_id})
    ).mappings().all()
    if len(rows) != 1:
        raise ControlledSeedError(f"expected exactly one pending candidate-bound review, found {len(rows)}")
    review = rows[0]
    metadata = review["review_metadata"] or {}
    bound = metadata.get("candidate_binding")
    if not (
        metadata.get("trust_candidate_required") is True
        and metadata.get("trust_kind") != "structured_source"
        and isinstance(bound, dict)
    ):
        raise ControlledSeedError("the pending review is not bound to an analysis candidate")
    if (await session.execute(_LEDGER_EXISTS)).scalar_one():
        decided = (
            await session.execute(_LEDGER_ROWS, {"t": tenant_id, "r": review["id"]})
        ).scalar_one()
        if decided:
            raise ControlledSeedError("the review already has finding decisions; the candidate is not replaced")

    binding = CandidateBinding(
        artifact_id=UUID(str(bound["artifact_id"])),
        document_id=document_id,
        artifact_version=int(bound["artifact_version"]),
        artifact_hash=str(bound["artifact_hash"]),
    )
    current = await session.get(DocumentArtifactORM, binding.artifact_id)
    if (
        current is None
        or current.tenant_id != tenant_id
        or current.trust_state != TrustState.PROPOSED.value
    ):
        raise ControlledSeedError("the bound candidate is not a PROPOSED artifact of this tenant")

    corrected = DocumentArtifact.model_validate(current.payload).model_copy(
        update={"extracted_risks": controlled_risks()}
    )
    new_binding = await SqlAlchemyDocumentArtifactRepository(session).propose_correction(
        binding, corrected, tenant_id=TenantId(tenant_id), review_row_id=review["id"]
    )
    return {
        "evidence_class": EVIDENCE_CLASS,
        "review_row_id": str(review["id"]),
        "superseded_artifact_id": str(binding.artifact_id),
        "artifact_id": str(new_binding.artifact_id),
        "artifact_version": new_binding.artifact_version,
        "artifact_hash": new_binding.artifact_hash,
        "findings": [
            {"ordinal": i, "title": risk["title"], "category": risk["category"]}
            for i, risk in enumerate(CONTROLLED_RISKS)
        ],
    }


def require_nonproduction() -> None:
    if os.getenv("ENVIRONMENT", "").lower() != "test" or os.getenv("C2PRO_AI_MOCK") != "1":
        raise ControlledSeedError(
            "the controlled candidate is nonproduction only: ENVIRONMENT=test and C2PRO_AI_MOCK=1 are required"
        )


async def run(tenant_id: UUID, document_id: UUID) -> dict[str, Any]:
    require_nonproduction()
    await init_db()
    try:
        async with get_session_with_tenant(tenant_id) as session:
            return await seed_controlled_findings(session, tenant_id=tenant_id, document_id=document_id)
    finally:
        await close_db()


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: python -m scripts.seed_controlled_s5_findings <tenant_id> <document_id>", file=sys.stderr)
        return 2
    try:
        report = asyncio.run(run(UUID(argv[1]), UUID(argv[2])))
    except (ControlledSeedError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    print(json.dumps({"ok": True, **report}))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv))
