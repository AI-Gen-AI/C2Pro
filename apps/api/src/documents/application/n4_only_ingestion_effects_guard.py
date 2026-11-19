"""Two-phase, fail-closed marker for recovering a killed N4-only INGESTION.

Ingestion may call an external embedding service before finish_ingestion. The
absence of N4 receipts cannot prove that no such call happened. This marker
is committed in the SAME transaction as ADOPT/ACQUIRE and before any
ingestion side effects, then is durably changed to MAY_HAVE_OCCURRED in a
separate fenced transaction BEFORE entering _ingest_owned. Only the first
state is eligible for a post-ADOPT expired-lease takeover.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.analysis.application.n4_only_pilot_policy import (
    N4OnlyPilotDenied,
    N4OnlyPilotScope,
    require_marked_pilot,
)
from src.core import processing_authority
from src.core.processing_authority import ProcessingAuthority, ProcessingStage
from src.documents.domain.models import DocumentStatus


class N4OnlyIngestionEffectsUnsafe(RuntimeError):
    """Potential effects occurred, or the pre-effects signal is unverifiable."""


BEFORE_EFFECTS = "ADOPTED_BEFORE_EFFECTS"
MAY_HAVE_OCCURRED = "EFFECTS_MAY_HAVE_OCCURRED"
GUARD_KEY = "ingestion_effects_guard"


def manual_claim_required(document: Any, authority: object | None) -> bool:
    """Prevent a broker redelivery from automatically stealing an old RUNNING.

    A marked pilot can acquire without an exact recovery authority only for
    its FIRST delivery, while still UPLOADED and without any prior attempt
    marker. Every PARSING/other-status redelivery (including legacy missing
    markers) or every previously adopted attempt needs manual recovery.
    """
    marker = (document.document_metadata or {}).get("n4_only_pilot")
    return (
        isinstance(marker, dict)
        and authority is None
        and (
            document.upload_status is not DocumentStatus.UPLOADED
            or GUARD_KEY in marker
        )
    )


def _authorized_marker(document: Any, grant: ProcessingAuthority) -> dict[str, Any]:
    metadata = document.document_metadata or {}
    marker = metadata.get("n4_only_pilot")
    if not isinstance(marker, dict):
        raise N4OnlyIngestionEffectsUnsafe("N4-only marker missing")
    try:
        scope = N4OnlyPilotScope.from_environment()
        require_marked_pilot(
            marker,
            tenant_id=grant.tenant_id,
            project_id=document.project_id,
            document_id=grant.document_id,
            revision_id=grant.revision_id,
            generation=grant.generation,
        )
        if (
            grant.stage is not ProcessingStage.INGESTION
            or grant.revision_id != scope.revision_id
            or grant.fencing_token <= scope.predecessor_fence
            or metadata.get("parsed_text_revision_id") != str(scope.revision_id)
            or marker.get("state") != "QUEUED"
        ):
            raise N4OnlyIngestionEffectsUnsafe("N4-only ingestion scope changed")
    except N4OnlyPilotDenied as exc:
        raise N4OnlyIngestionEffectsUnsafe("N4-only processing policy rejected") from exc
    return marker


def _guard_identity(grant: ProcessingAuthority) -> dict[str, Any]:
    return {
        "document_revision_id": str(grant.revision_id),
        "generation": grant.generation,
        "fencing_token": grant.fencing_token,
        "attempt_id": str(grant.attempt_id),
    }


def _same_attempt(guard: object, grant: ProcessingAuthority) -> bool:
    return isinstance(guard, dict) and all(
        guard.get(key) == value
        for key, value in _guard_identity(grant).items()
    )


async def record_before_ingestion_effects(
    *, repo: Any, document: Any, grant: ProcessingAuthority
) -> None:
    """Stage BEFORE_EFFECTS in the SAME transaction as the ADOPT DB grant.

    Caller MUST commit *after* this metadata update, *before* any ingestion
    work. Missing history is acceptable only for a freshly adopted grant; a
    prior MAY_HAVE_OCCURRED history is never reset/overwritten.
    """
    marker = _authorized_marker(document, grant)
    previous = marker.get(GUARD_KEY)
    if previous is not None and (
        not isinstance(previous, dict)
        or previous.get("state") != BEFORE_EFFECTS
        or previous.get("document_revision_id") != str(grant.revision_id)
        or previous.get("generation") != grant.generation
        or not isinstance(previous.get("fencing_token"), int)
        or previous["fencing_token"] >= grant.fencing_token
    ):
        raise N4OnlyIngestionEffectsUnsafe("prior ingestion may have effects; STOP")

    next_marker = dict(marker)
    next_marker[GUARD_KEY] = {
        **_guard_identity(grant),
        "state": BEFORE_EFFECTS,
        "recorded_at_utc": datetime.now(UTC).isoformat(),
    }
    metadata = {**(document.document_metadata or {}), "n4_only_pilot": next_marker}
    await repo.update_metadata(grant.tenant_id, grant.document_id, metadata)
    document.document_metadata = metadata


async def record_ingestion_effects_possible(
    *, repo: Any, document: Any, grant: ProcessingAuthority
) -> None:
    """Durably seal UNSAFE BEFORE the FIRST potentially external side effect.

    Verify the exact active worker authority under DB row lock before writing.
    Do not enter _ingest_owned unless this commit succeeds. A crash before
    this commit is the ONLY post-ADOPT RUNNING state eligible for rescue.
    """
    marker = _authorized_marker(document, grant)
    guard = marker.get(GUARD_KEY)
    if not _same_attempt(guard, grant) or guard.get("state") != BEFORE_EFFECTS:
        raise N4OnlyIngestionEffectsUnsafe("missing or stale pre-effect attestation")
    await processing_authority.verify_in_transaction(repo.session, grant)
    next_marker = dict(marker)
    next_marker[GUARD_KEY] = {
        **_guard_identity(grant),
        "state": MAY_HAVE_OCCURRED,
        "recorded_at_utc": datetime.now(UTC).isoformat(),
    }
    metadata = {**(document.document_metadata or {}), "n4_only_pilot": next_marker}
    await repo.update_metadata(grant.tenant_id, grant.document_id, metadata)
    await repo.commit()
    document.document_metadata = metadata
