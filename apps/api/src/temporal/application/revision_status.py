"""Trust, currency and materialization status of one revision (Lane C / C3b-2).

A read model for the What Changed surface, assembled from the authorities that
already own each fact -- it decides nothing:

* ``trust_state`` -- the #714 trust state of the artifact bound to the revision
  (``document_artifacts``); ``None`` when no artifact is bound to it;
* ``is_current`` -- whether the C3a trusted-current resolver points at this
  revision. A revision whose candidate is still proposed is NOT current: the
  previously trusted revision stays canonical until the exact candidate is
  approved;
* ``materialization`` -- the C3b-1 artifact-keyed obligation. ``materialized``
  means every effect governance currently authorises was applied, NOT that every
  proposed effect became canonical: ``deferred_effects`` names what still waits
  for its own governance (e.g. the WBS proposal) and where it is recoverable.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class MaterializationStatus(BaseModel):
    # not_required | pending | materialized | obsolete | operator_required
    state: str
    scope: str | None = None
    qualifications: list[str] = Field(default_factory=list)
    deferred_effects: dict[str, Any] = Field(default_factory=dict)


class RevisionStatus(BaseModel):
    status: Literal["available", "unavailable"] = "available"
    revision_id: UUID
    rev_no: int | None = None
    # proposed | trusted | rejected | superseded; None when no artifact is bound.
    trust_state: str | None = None
    artifact_id: UUID | None = None
    artifact_version: int | None = None
    is_current: bool = False
    current_revision_id: UUID | None = None
    # trusted | single_revision | unresolved (C3a resolver basis)
    current_basis: str = "unresolved"
    materialization: MaterializationStatus | None = None
    reason: str | None = None

    @classmethod
    def unavailable(cls, revision_id: UUID, reason: str) -> RevisionStatus:
        return cls(status="unavailable", revision_id=revision_id, reason=reason)


def materialization_from_row(state: object, detail: object) -> MaterializationStatus | None:
    if not isinstance(state, str) or not state:
        return None
    body = detail if isinstance(detail, dict) else {}
    qualifications = body.get("qualifications")
    deferred = body.get("deferred_effects")
    scope = body.get("scope")
    return MaterializationStatus(
        state=state,
        scope=scope if isinstance(scope, str) else None,
        qualifications=[str(q) for q in qualifications] if isinstance(qualifications, list) else [],
        deferred_effects=deferred if isinstance(deferred, dict) else {},
    )


__all__ = ["MaterializationStatus", "RevisionStatus", "materialization_from_row"]
