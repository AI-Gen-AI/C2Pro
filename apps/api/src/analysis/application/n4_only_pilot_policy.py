"""Fail-closed, document-scoped N4 pilot authorization.

No user-controlled switch or global route toggle: the server owner must provision
a pinned, expiring scope explicitly. Absence of the scope disables the pilot.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

_SHA = re.compile(r"^[0-9a-f]{64}$")


class N4OnlyPilotDenied(RuntimeError):
    """The target, caller, source, lineage or environment is not authorized."""


def _uuid(value: object) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise N4OnlyPilotDenied("invalid pilot identity") from exc


@dataclass(frozen=True)
class N4OnlyPilotScope:
    tenant_id: UUID
    project_id: UUID
    document_id: UUID
    revision_id: UUID
    source_sha256: str
    approved_user_id: UUID
    predecessor_generation: int
    predecessor_fence: int
    expected_windows: int
    expires_at: datetime

    @property
    def next_generation(self) -> int:
        return self.predecessor_generation + 1

    @property
    def digest(self) -> str:
        parts = (
            str(self.tenant_id), str(self.project_id), str(self.document_id),
            str(self.revision_id), self.source_sha256, str(self.approved_user_id),
            str(self.predecessor_generation), str(self.predecessor_fence),
            str(self.expected_windows), self.expires_at.isoformat(),
        )
        return hashlib.sha256("|".join(parts).encode()).hexdigest()

    @classmethod
    def from_environment(cls) -> N4OnlyPilotScope:
        raw = os.getenv("C2PRO_N4_ONLY_APPROVED_SCOPE")
        if not raw:
            raise N4OnlyPilotDenied("N4-only scope not provisioned")
        if (
            os.getenv("RAILWAY_ENVIRONMENT_NAME", "").lower() != "pilot"
            or os.getenv("RAILWAY_ENVIRONMENT_ID")
            != os.getenv("C2PRO_N4_UAT_APPROVED_RAILWAY_ENVIRONMENT_ID")
            or not os.getenv("RAILWAY_ENVIRONMENT_ID")
        ):
            raise N4OnlyPilotDenied("N4-only permitted only in pinned UAT environment")
        try:
            obj = json.loads(raw)
            if not isinstance(obj, dict):
                raise ValueError("object required")
            expiration = datetime.fromisoformat(str(obj["expires_at"]).replace("Z", "+00:00"))
            scope = cls(
                tenant_id=_uuid(obj["tenant_id"]),
                project_id=_uuid(obj["project_id"]),
                document_id=_uuid(obj["document_id"]),
                revision_id=_uuid(obj["revision_id"]),
                source_sha256=str(obj["source_sha256"]),
                approved_user_id=_uuid(obj["approved_user_id"]),
                predecessor_generation=int(obj["predecessor_generation"]),
                predecessor_fence=int(obj["predecessor_fence"]),
                expected_windows=int(obj["expected_windows"]),
                expires_at=expiration,
            )
        except (ValueError, TypeError, KeyError) as exc:
            raise N4OnlyPilotDenied("invalid pinned N4-only policy") from exc
        if (
            not _SHA.fullmatch(scope.source_sha256)
            or scope.expires_at.tzinfo is None
            or scope.expires_at <= datetime.now(UTC)
            or scope.predecessor_generation < 1
            or scope.predecessor_fence < 1
            or scope.expected_windows != 23
            or scope.tenant_id != _uuid(os.getenv("C2PRO_N4_UAT_APPROVED_TENANT_ID"))
        ):
            raise N4OnlyPilotDenied("N4-only scope expired or not approved")
        return scope

    def check_target(
        self, *, tenant_id: object, project_id: object, document_id: object,
        revision_id: object, generation: int, scope_digest: str,
        user_id: object | None = None,
    ) -> None:
        if (
            _uuid(tenant_id) != self.tenant_id
            or _uuid(project_id) != self.project_id
            or _uuid(document_id) != self.document_id
            or _uuid(revision_id) != self.revision_id
            or type(generation) is not int or generation != self.next_generation
            or scope_digest != self.digest
            or (user_id is not None and _uuid(user_id) != self.approved_user_id)
        ):
            raise N4OnlyPilotDenied("N4-only pilot scope, source or lineage mismatch")


def pilot_marker(scope: N4OnlyPilotScope) -> dict[str, str | int]:
    return {
        "scope_digest": scope.digest,
        "revision_id": str(scope.revision_id),
        "generation": scope.next_generation,
        "source_sha256": scope.source_sha256,
        "state": "QUEUED",
    }


def require_marked_pilot(
    marker: object, *, tenant_id: object, project_id: object,
    document_id: object, revision_id: object, generation: int,
) -> N4OnlyPilotScope:
    if not isinstance(marker, dict):
        raise N4OnlyPilotDenied("N4-only pilot marker missing")
    scope = N4OnlyPilotScope.from_environment()
    scope.check_target(
        tenant_id=tenant_id, project_id=project_id, document_id=document_id,
        revision_id=revision_id, generation=generation,
        scope_digest=str(marker.get("scope_digest") or ""),
    )
    if (
        marker.get("revision_id") != str(scope.revision_id)
        or marker.get("source_sha256") != scope.source_sha256
        or marker.get("generation") != scope.next_generation
        or marker.get("state") not in ("QUEUED", "PROPOSED_N12_UNASSESSED", "NO_FINDINGS_UNASSESSED")
    ):
        raise N4OnlyPilotDenied("N4-only marker is incomplete or changed")
    return scope
