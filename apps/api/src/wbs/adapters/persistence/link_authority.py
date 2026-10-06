"""PC-2a.3 (#897): WBS link-write authority -- RACI and BOM links bind only to approved scope.

A new link (``stakeholder_wbs_raci`` / ``procurement_bom_items.wbs_item_id``) may target only a
node of the project's CURRENT approved baseline. NO_WBS, DRAFT_ONLY and LEGACY_UNGOVERNED projects
take no new links (``WBS_NOT_APPROVED``). A retired node, another project's node or an id unknown
to the tenant is ``WBS_NODE_NOT_CURRENT_BASELINE``; cross-tenant existence is never revealed. A
change-set candidate is ``WBS_CANDIDATE_NOT_CANONICAL``. Existing links are never touched.

Race safety: the check and the insert run in the caller's transaction. The gate first takes
``FOR KEY SHARE`` on the ``projects`` row, which conflicts only with the ``FOR UPDATE`` that
approve = apply takes before anything else, so the two serialize:
- apply first: this gate waits, then (READ COMMITTED) reads the new baseline and refuses a
  retired node;
- link first: the apply waits, then its retired-node link check sees the link and refuses.
Lock order is always project row, then ``wbs_nodes`` rows (the FK check), as in the apply: no
deadlock. Authority is resolved once per project per transaction, after the lock (which pins
it), and never cached across transactions.
"""

from __future__ import annotations

import weakref
from collections.abc import Collection
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import SessionTransaction

from src.core.exceptions import C2ProException
from src.wbs.adapters.persistence.governance_repository import WBSGovernanceRepository
from src.wbs.domain.governance import WBSAuthority

NOT_APPROVED = "WBS_NOT_APPROVED"
NODE_NOT_CURRENT_BASELINE = "WBS_NODE_NOT_CURRENT_BASELINE"
CANDIDATE_NOT_CANONICAL = "WBS_CANDIDATE_NOT_CANONICAL"


class WBSNotApprovedError(C2ProException):
    def __init__(self, project_id: UUID, authority: WBSAuthority) -> None:
        super().__init__(
            message=("The project has no approved WBS baseline: new links bind only to approved WBS scope "
                     "(approve a WBS change set first)."),
            code=NOT_APPROVED, status_code=409,
            details={"project_id": str(project_id), "authority_state": authority.display_state},
        )


class WBSNodeNotCurrentBaselineError(C2ProException):
    def __init__(self, project_id: UUID) -> None:
        super().__init__(
            message="The WBS node is not part of the project's current approved WBS baseline.",
            code=NODE_NOT_CURRENT_BASELINE, status_code=409, details={"project_id": str(project_id)},
        )


class WBSCandidateNotCanonicalError(C2ProException):
    def __init__(self, project_id: UUID) -> None:
        super().__init__(
            message="The WBS node is only a change-set candidate; candidates are never canonical project scope.",
            code=CANDIDATE_NOT_CANONICAL, status_code=409, details={"project_id": str(project_id)},
        )


# Per root transaction: project -> authority resolved under this transaction's project-row lock.
_locked_authority: weakref.WeakKeyDictionary[SessionTransaction, dict[tuple[UUID, UUID], WBSAuthority]] = (
    weakref.WeakKeyDictionary()
)

_PROJECT_OF_LIVE = text("SELECT project_id FROM wbs_nodes WHERE id = :n AND tenant_id = :t")
_PROJECT_OF_BASELINE = text(
    "SELECT project_id FROM wbs_baseline_nodes WHERE node_id = :n AND tenant_id = :t LIMIT 1")
_PROJECT_OF_RETIREMENT = text(
    "SELECT project_id FROM wbs_change_set_retirements WHERE node_id = :n AND tenant_id = :t LIMIT 1")
_PROJECT_OF_CANDIDATE = text(
    "SELECT project_id FROM wbs_change_set_nodes WHERE node_id = :n AND tenant_id = :t LIMIT 1")
_LOCK_PROJECT = text("SELECT id FROM projects WHERE id = :p AND tenant_id = :t FOR KEY SHARE")
_CURRENT_NODES = text(
    "SELECT b.node_id FROM wbs_baseline_nodes b "
    "JOIN wbs_nodes w ON w.id = b.node_id AND w.project_id = b.project_id AND w.tenant_id = b.tenant_id "
    "WHERE b.baseline_id = :b AND b.project_id = :p AND b.tenant_id = :t AND b.node_id = ANY(:ids)")
_EVER_BASELINED = text(
    "SELECT DISTINCT node_id FROM wbs_baseline_nodes "
    "WHERE project_id = :p AND tenant_id = :t AND node_id = ANY(:ids)")
_CANDIDATES = text(
    "SELECT DISTINCT node_id FROM wbs_change_set_nodes "
    "WHERE project_id = :p AND tenant_id = :t AND node_id = ANY(:ids)")


async def project_of_wbs_node(session: AsyncSession, tenant_id: UUID, node_id: UUID) -> UUID | None:
    """The tenant's project a WBS id belongs to (live, baselined, retired or candidate); None if unknown."""
    params = {"n": node_id, "t": tenant_id}
    for query in (_PROJECT_OF_LIVE, _PROJECT_OF_BASELINE, _PROJECT_OF_RETIREMENT, _PROJECT_OF_CANDIDATE):
        project_id = await session.scalar(query, params)
        if project_id is not None:
            return UUID(str(project_id))
    return None


def _innermost(session: AsyncSession) -> SessionTransaction | None:
    sync = session.sync_session
    return sync.get_nested_transaction() or sync.get_transaction()


async def _authority_under_lock(session: AsyncSession, tenant_id: UUID, project_id: UUID) -> WBSAuthority | None:
    key = (tenant_id, project_id)
    # A lock taken in this transaction or an enclosing one is still held (a rolled-back
    # savepoint releases its own locks, so its entry is never consulted again).
    transaction = _innermost(session)
    while transaction is not None:
        cached = _locked_authority.get(transaction, {}).get(key)
        if cached is not None:
            return cached
        transaction = transaction.parent
    if await session.scalar(_LOCK_PROJECT, {"p": project_id, "t": tenant_id}) is None:
        return None
    authority = await WBSGovernanceRepository(session).authority(project_id, tenant_id)
    holder = _innermost(session)
    if holder is not None:
        _locked_authority.setdefault(holder, {})[key] = authority
    return authority


async def require_linkable_wbs_nodes(
    session: AsyncSession, *, tenant_id: UUID, project_id: UUID, node_ids: Collection[UUID]
) -> WBSAuthority:
    """Refuse (409) unless every node is in ``project_id``'s current approved baseline.

    Must run in the transaction that inserts the link(s); the project-row lock it takes is held
    until that transaction ends.
    """
    ids = list(dict.fromkeys(node_ids))
    authority = await _authority_under_lock(session, tenant_id, project_id)
    if authority is None:  # the project is not the caller tenant's: nothing in it is linkable
        raise WBSNodeNotCurrentBaselineError(project_id)
    if not authority.approved:
        raise WBSNotApprovedError(project_id, authority)
    if not ids:
        return authority
    params: dict[str, Any] = {"b": authority.baseline_id, "p": project_id, "t": tenant_id, "ids": ids}
    current = {row[0] for row in await session.execute(_CURRENT_NODES, params)}
    missing = [node_id for node_id in ids if node_id not in current]
    if missing:
        baselined = {row[0] for row in await session.execute(_EVER_BASELINED, {**params, "ids": missing})}
        candidates = {row[0] for row in await session.execute(_CANDIDATES, {**params, "ids": missing})}
        if all(node_id in candidates and node_id not in baselined for node_id in missing):
            raise WBSCandidateNotCanonicalError(project_id)
        raise WBSNodeNotCurrentBaselineError(project_id)
    return authority


__all__ = [
    "CANDIDATE_NOT_CANONICAL",
    "NODE_NOT_CURRENT_BASELINE",
    "NOT_APPROVED",
    "WBSCandidateNotCanonicalError",
    "WBSNodeNotCurrentBaselineError",
    "WBSNotApprovedError",
    "project_of_wbs_node",
    "require_linkable_wbs_nodes",
]
