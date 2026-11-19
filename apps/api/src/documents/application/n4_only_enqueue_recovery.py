"""Manual, fail-closed redrive of a stranded N4-only INGESTION enqueue.

A recovery is NOT a reprocess: it cannot bump the generation, approve HITL,
run N12, or change AI budgets. The existing DB-clock CLAIMED/ADOPTED processing
authority ensures only one worker can enter the inherited ingestion stage.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text

from src.analysis.application.n4_only_pilot_policy import (
    N4OnlyPilotDenied,
    N4OnlyPilotScope,
    require_marked_pilot,
)
from src.core import processing_authority
from src.core.processing_authority import ProcessingAuthority, ProcessingStage
from src.documents.domain.models import DocumentStatus, DocumentType


class N4OnlyEnqueueRecoveryDenied(RuntimeError):
    """No recovery is permitted; never enqueue or reserve a provider call."""


@dataclass(frozen=True)
class RecoveryClaim:
    authority: ProcessingAuthority
    revision_id: UUID
    generation: int


# A current-gen run may already carry ambiguous provider activity even if it
# has zero visible receipts. No recalc, no N4-run replay and no reprocess.
_CURRENT_RUN_EXISTS = text("""
    SELECT EXISTS (
        SELECT 1 FROM public.n4_extraction_runs r
         WHERE r.tenant_id = CAST(:tenant AS uuid)
           AND r.document_id = CAST(:document AS uuid)
           AND r.generation = :generation
    )
""")

# Any prior document receipt is a liability until separately reconciled;
# the route is only for CAS -> enqueue gaps, before ANY N4 work can exist.
_ANY_N4_RECEIPT = text("""
    SELECT EXISTS (
        SELECT 1
          FROM public.n4_usage_reservations receipt
          JOIN public.n4_extraction_runs run
            ON run.tenant_id = receipt.tenant_id
           AND run.run_id = receipt.run_id
         WHERE run.tenant_id = CAST(:tenant AS uuid)
           AND run.document_id = CAST(:document AS uuid)
    )
""")

_LOCK_DOCUMENT = text("""
    SELECT id FROM public.documents
     WHERE tenant_id = CAST(:tenant AS uuid)
       AND id = CAST(:document AS uuid)
     FOR UPDATE
""")

_CURRENT_AUTHORITY = text("""
    SELECT revision_id, generation, stage, phase, fencing_token, attempt_count,
           lease_expires_at,
           (lease_expires_at IS NOT NULL AND
            lease_expires_at > (clock_timestamp() AT TIME ZONE 'UTC')) AS lease_valid
      FROM public.document_processing_operations
     WHERE tenant_id = CAST(:tenant AS uuid)
       AND document_id = CAST(:document AS uuid)
     FOR UPDATE
""")

_ACTIVE_REVISION = text("""
    SELECT EXISTS (
        SELECT 1 FROM public.document_revisions
         WHERE tenant_id = CAST(:tenant AS uuid)
           AND document_id = CAST(:document AS uuid)
           AND revision_id = CAST(:revision AS uuid)
           AND valid_to IS NULL
    )
""")

MAX_MANUAL_RECOVERY_CLAIMS = 2


async def claim_stranded_n4_enqueue(
    *,
    repo: Any,
    tenant_id: UUID,
    project_id: UUID,
    document_id: UUID,
    user_id: UUID,
) -> RecoveryClaim:
    """Authorize, check NO provider history and claim a fenced INGESTION grant.

    The caller is responsible for COMMITTING the updated metadata + DB grant
    before trying Celery; the dispatch is deliberately not inside the DB TX.
    If dispatch is ambiguous, a second grant is forbidden while the previous
    lease is valid. After lease expiry, a NEW manual request may claim once
    more (bounded by MAX_MANUAL_RECOVERY_CLAIMS).
    """
    if os.getenv("C2PRO_N4_ONLY_MANUAL_RECOVERY_ENABLED") != "1":
        raise N4OnlyEnqueueRecoveryDenied("manual recovery disabled by operator")

    try:
        scope = N4OnlyPilotScope.from_environment()  # EXPIRED -> DENY (execution)
        scope.check_target(
            tenant_id=tenant_id, project_id=project_id, document_id=document_id,
            revision_id=scope.revision_id, generation=scope.next_generation,
            scope_digest=scope.digest, user_id=user_id,
        )
    except N4OnlyPilotDenied as exc:
        raise N4OnlyEnqueueRecoveryDenied("invalid/expired manual recovery grant") from exc

    session = repo.session
    args = {"tenant": str(tenant_id), "document": str(document_id)}
    # Canonical documents -> operation lock order; all checks and claim
    # execute on the same DB transaction. No writes on a failed preflight.
    locked = (await session.execute(_LOCK_DOCUMENT, args)).first()
    if locked is None:
        raise N4OnlyEnqueueRecoveryDenied("document does not exist in tenant")

    doc = await repo.get_by_id(tenant_id, document_id)
    marker = (getattr(doc, "document_metadata", None) or {}).get("n4_only_pilot")
    try:
        require_marked_pilot(
            marker, tenant_id=tenant_id, project_id=project_id,
            document_id=document_id, revision_id=scope.revision_id,
            generation=scope.next_generation,
        )
    except N4OnlyPilotDenied as exc:
        raise N4OnlyEnqueueRecoveryDenied("pilot marker is not QUEUED/authorized") from exc
    if (
        doc is None
        or doc.project_id != project_id
        or doc.document_type != DocumentType.CONTRACT
        or doc.upload_status != DocumentStatus.UPLOADED
        or marker.get("state") != "QUEUED"
        or (doc.document_metadata or {}).get("parsed_text_revision_id") != str(scope.revision_id)
    ):
        raise N4OnlyEnqueueRecoveryDenied("not a stranded queued R1 pilot")

    if not (await session.execute(
        _ACTIVE_REVISION, args | {"revision": str(scope.revision_id)}
    )).scalar_one():
        raise N4OnlyEnqueueRecoveryDenied("R1 no longer active")

    row = (await session.execute(_CURRENT_AUTHORITY, args)).mappings().one_or_none()
    if (
        row is None
        or str(row["revision_id"]) != str(scope.revision_id)
        or row["generation"] != scope.next_generation
        or str(row["stage"]) != "INGESTION"
        or str(row["phase"]) not in ("PENDING", "CLAIMED")
        or bool(row["lease_valid"])
        or int(row["fencing_token"]) <= scope.predecessor_fence
        or int(row["attempt_count"]) >= MAX_MANUAL_RECOVERY_CLAIMS
    ):
        raise N4OnlyEnqueueRecoveryDenied("processing generation owned/stale or recovery exhausted")

    if (await session.execute(
        _CURRENT_RUN_EXISTS, args | {"generation": scope.next_generation}
    )).scalar_one():
        raise N4OnlyEnqueueRecoveryDenied("N4 run exists; no enqueue recovery")

    if (await session.execute(_ANY_N4_RECEIPT, args)).scalar_one():
        raise N4OnlyEnqueueRecoveryDenied("provider receipt exists; reconciliation required")

    # The canonical claim increments FENCE under the DB-clock lease and mints
    # a single-use owner token. Exactly one delivery may ADOPT it, including
    # under concurrent POSTs or duplicate Celery broker deliveries.
    grant = await processing_authority.claim_for_recovery(
        session, tenant_id=tenant_id, document_id=document_id,
        stage=ProcessingStage.INGESTION, revision_id=scope.revision_id,
    )
    if (
        grant is None
        or grant.generation != scope.next_generation
        or grant.stage is not ProcessingStage.INGESTION
        or grant.revision_id != scope.revision_id
        or grant.fencing_token <= int(row["fencing_token"])
    ):
        raise N4OnlyEnqueueRecoveryDenied("recovery claim failed or lost its fence")

    # Append a bounded, durable operator/audit stamp in the SAME transaction
    # as the recovery claim. No task secret/owner token is recorded here.
    metadata = dict(doc.document_metadata or {})
    pilot = dict(marker)
    events = list(pilot.get("enqueue_recovery_events") or [])
    if len(events) >= MAX_MANUAL_RECOVERY_CLAIMS:
        raise N4OnlyEnqueueRecoveryDenied("manual recovery audit limit exceeded")
    events.append({
        "actor_user_id": str(user_id),
        "generation": scope.next_generation,
        "previous_fence": int(row["fencing_token"]),
        "claimed_fence": grant.fencing_token,
        "attempt_id": str(grant.attempt_id),
        "event": "manual_enqueue_recovery_claimed",
        "observed_at_utc": datetime.now(UTC).isoformat(),
    })
    pilot["enqueue_recovery_events"] = events
    metadata["n4_only_pilot"] = pilot
    await repo.update_metadata(tenant_id, document_id, metadata)
    return RecoveryClaim(
        authority=grant, revision_id=scope.revision_id, generation=grant.generation
    )
