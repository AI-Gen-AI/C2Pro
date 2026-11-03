"""ADR-032 x S5-02 against real PostgreSQL: a grant revoked while the structured-source approval is in flight.

The first check of ``APPROVE_CANDIDATE`` happens at the top of ``DecideStructuredSourceTrustService.execute``. The APPROVE
branch then re-reads and re-parses the immutable source (file I/O: seconds on a large workbook) before it promotes the
candidate. A check taken at the top and acted on much later is a time-of-check/time-of-use window: a revocation committed in
between would still promote the candidate.

What is proven, with independent database sessions (so the locks are real, not simulated):

* a revocation committed AFTER the first check and BEFORE the promotion denies the approval and leaves the candidate PROPOSED;
* a revocation racing the promotion transaction waits for it (the grant row is held FOR SHARE) and cannot slip in between the
  last check and the TRUSTED write: the promotion commits under a grant that was valid inside its own transaction;
* a revocation that already holds the grant row (uncommitted) makes the approval wait and then deny it once it is committed;
* the grant row is NOT locked while the source is being parsed (the revalidation sits next to the promotion, not at the top);
* the positive ENFORCE path promotes with a valid grant; grants do not cross projects; REJECT never needs the revalidation;
* no deadlock between approval and revocation across many interleavings (lock order: document -> project -> review ->
  artifact -> grant, the same as the S5-05 promotion).
"""

from __future__ import annotations

import asyncio
import random
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.document_artifact_repository import (
    SqlAlchemyDocumentArtifactRepository,
)
from src.analysis.application.structured_source_trust import (
    ImmutableStructuredSourceVerifier,
    StructuredTrustForbidden,
)
from src.core.auth.models import Tenant, User, UserRole
from src.modules.hitl.adapters.persistence.project_review_grants import ProjectReviewGrantRepository
from src.modules.hitl.application.project_review_authorization import ProjectCapability
from tests.modules.integration.grants_world import apply_grants_schema
from tests.modules.integration.test_adr032_structured_source_trust_pg import (
    _approver,
    _artifact,
    _count,
    _decide,
    _document,
    _request,
    _Storage,
    _world,
)

pytestmark = pytest.mark.asyncio

APPROVE, READ = ProjectCapability.APPROVE_CANDIDATE, ProjectCapability.READ_REVIEW


async def _enforce_with_grants(db: AsyncSession, w: dict, approver: UUID, *capabilities: ProjectCapability, project: UUID | None = None) -> dict[ProjectCapability, UUID]:
    """The tenant in ENFORCE and ``approver`` holding exactly ``capabilities`` on the project (default: the candidate's)."""
    await apply_grants_schema(db)
    await db.execute(
        update(Tenant).where(Tenant.id == w["tenant"]).values(settings={"hitl_project_authorization": {"mode": "enforce"}})
    )
    grantor = await db.scalar(
        select(User.id).where(User.tenant_id == w["tenant"], User.role == UserRole.ADMIN, User.id != approver)
    )
    assert grantor is not None
    out: dict[ProjectCapability, UUID] = {}
    for capability in capabilities:
        out[capability] = await ProjectReviewGrantRepository(db).grant(
            tenant_id=w["tenant"], project_id=project or w["project"], user_id=approver, capability=capability,
            granted_by=grantor, reason=f"{capability.value} for the race tests",
        )
    await db.commit()
    return out


async def _revoke(factory: Any, w: dict, grant_id: UUID, *, commit: bool = True) -> None:
    async with factory() as session:
        admin = await session.scalar(select(User.id).where(User.tenant_id == w["tenant"], User.role == UserRole.ADMIN).limit(1))
        await ProjectReviewGrantRepository(session).revoke(
            tenant_id=w["tenant"], grant_id=grant_id, revoked_by=admin, reason="revoked while the approval is in flight"
        )
        if commit:
            await session.commit()


async def _decided_events(factory: Any, w: dict) -> int:
    return await _count(
        factory,
        "SELECT count(*) FROM project_events WHERE project_id = cast(:p as uuid) AND event_type = 'structured_source.trust_decided'",
        p=str(w["project"]),
    )


async def _setup(db: AsyncSession, factory: Any, tmp_path: Path, *capabilities: ProjectCapability):
    w, storage = await _world(db, tmp_path), _Storage()
    approver = await _approver(db, w)
    doc = await _document(db, w, tmp_path, storage)
    receipt = await _request(factory, storage, w, doc)  # the request runs before ENFORCE: it is not what is under test
    grants = await _enforce_with_grants(db, w, approver, *capabilities)
    return w, storage, approver, doc, receipt, grants


async def test_a_revocation_committed_between_the_check_and_the_promotion_denies_the_approval(
    db: AsyncSession, test_session_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE window: the first check passed, the grant is revoked while the source is parsed, the promotion must not happen."""
    w, storage, approver, _doc, receipt, grants = await _setup(db, test_session_factory, tmp_path, READ, APPROVE)
    real_verify = ImmutableStructuredSourceVerifier.verify
    revoked = {"n": 0}

    async def revoke_during_the_parse(self: Any, **kwargs: Any) -> Any:
        verified = await real_verify(self, **kwargs)
        await _revoke(test_session_factory, w, grants[APPROVE])  # committed from another session: must not block
        revoked["n"] += 1
        return verified

    monkeypatch.setattr(ImmutableStructuredSourceVerifier, "verify", revoke_during_the_parse)
    with pytest.raises(StructuredTrustForbidden) as denied:
        await asyncio.wait_for(_decide(test_session_factory, storage, w, receipt, "APPROVE", actor=approver), timeout=60)
    assert revoked["n"] == 1, "the grant was revoked after the first check and before the promotion"
    assert denied.value.code == "project_capability_required"
    assert (await _artifact(test_session_factory, receipt.artifact_id)).trust_state == "proposed", "nothing was promoted"
    assert await _decided_events(test_session_factory, w) == 0, "and no decision event was appended"


async def test_the_grant_row_is_not_locked_while_the_source_is_parsed(
    db: AsyncSession, test_session_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The revalidation sits next to the promotion: a revocation during the (long) parse is never made to wait for it."""
    w, storage, approver, _doc, receipt, grants = await _setup(db, test_session_factory, tmp_path, READ, APPROVE)
    real_verify = ImmutableStructuredSourceVerifier.verify
    waited: dict[str, float] = {}

    async def timed_revocation_during_the_parse(self: Any, **kwargs: Any) -> Any:
        verified = await real_verify(self, **kwargs)
        loop = asyncio.get_running_loop()
        started = loop.time()
        await asyncio.wait_for(_revoke(test_session_factory, w, grants[READ]), timeout=10)  # another grant of the same user
        waited["seconds"] = loop.time() - started
        return verified

    monkeypatch.setattr(ImmutableStructuredSourceVerifier, "verify", timed_revocation_during_the_parse)
    out = await _decide(test_session_factory, storage, w, receipt, "APPROVE", actor=approver)
    assert out.trust_state == "trusted"
    assert waited["seconds"] < 5, "revoking a grant is not blocked by an approval that is still parsing"


async def test_a_revocation_racing_the_promotion_waits_for_it_and_cannot_slip_in_between(
    db: AsyncSession, test_session_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    w, storage, approver, _doc, receipt, grants = await _setup(db, test_session_factory, tmp_path, READ, APPROVE)
    real_commit = SqlAlchemyDocumentArtifactRepository.commit_structured_candidate
    inside, release = asyncio.Event(), asyncio.Event()

    async def hold_inside_the_transaction(self: Any, *args: Any, **kwargs: Any) -> Any:
        inside.set()  # the grant was revalidated FOR SHARE just before this statement
        await asyncio.wait_for(release.wait(), timeout=30)
        return await real_commit(self, *args, **kwargs)

    monkeypatch.setattr(SqlAlchemyDocumentArtifactRepository, "commit_structured_candidate", hold_inside_the_transaction)
    approval = asyncio.create_task(_decide(test_session_factory, storage, w, receipt, "APPROVE", actor=approver))
    await asyncio.wait_for(inside.wait(), timeout=60)
    revocation = asyncio.create_task(_revoke(test_session_factory, w, grants[APPROVE]))
    done, _ = await asyncio.wait({revocation}, timeout=2.0)
    assert not done, "the revocation (an UPDATE of the grant row) waits for the promotion transaction"
    release.set()
    out = await asyncio.wait_for(approval, timeout=60)
    await asyncio.wait_for(revocation, timeout=30)
    assert out.trust_state == "trusted" and (await _artifact(test_session_factory, receipt.artifact_id)).trust_state == "trusted"
    assert await _count(
        test_session_factory, "SELECT count(*) FROM project_review_grants WHERE grant_id = cast(:g as uuid) AND revoked_at IS NOT NULL",
        g=str(grants[APPROVE]),
    ) == 1, "the promotion committed under a grant that was valid inside its transaction; the revocation took effect right after"


async def test_a_revocation_that_already_holds_the_grant_makes_the_approval_wait_and_then_denies_it(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    w, storage, approver, _doc, receipt, grants = await _setup(db, test_session_factory, tmp_path, READ, APPROVE)
    async with test_session_factory() as revoker:
        admin = await revoker.scalar(select(User.id).where(User.tenant_id == w["tenant"], User.role == UserRole.ADMIN).limit(1))
        await ProjectReviewGrantRepository(revoker).revoke(
            tenant_id=w["tenant"], grant_id=grants[APPROVE], revoked_by=admin, reason="revocation in flight"
        )  # not committed: this session holds the grant row
        approval = asyncio.create_task(_decide(test_session_factory, storage, w, receipt, "APPROVE", actor=approver))
        done, _ = await asyncio.wait({approval}, timeout=2.0)
        assert not done, "the approval cannot finish while an uncommitted revocation holds the grant"
        await revoker.commit()
    with pytest.raises(StructuredTrustForbidden) as denied:
        await asyncio.wait_for(approval, timeout=60)
    assert denied.value.code == "project_capability_required"
    assert (await _artifact(test_session_factory, receipt.artifact_id)).trust_state == "proposed"
    assert await _decided_events(test_session_factory, w) == 0


async def test_the_positive_enforce_path_promotes_exactly_once_with_the_valid_grant(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    w, storage, approver, _doc, receipt, _grants = await _setup(db, test_session_factory, tmp_path, READ, APPROVE)
    out = await _decide(test_session_factory, storage, w, receipt, "APPROVE", actor=approver)
    assert out.trust_state == "trusted" and not out.replayed
    replay = await _decide(test_session_factory, storage, w, receipt, "APPROVE", actor=approver)
    assert replay.replayed and replay.event_id == out.event_id
    assert await _decided_events(test_session_factory, w) == 1


async def test_a_grant_on_another_project_does_not_authorize_this_candidate(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    w, storage = await _world(db, tmp_path), _Storage()
    approver = await _approver(db, w)
    doc = await _document(db, w, tmp_path, storage)
    receipt = await _request(test_session_factory, storage, w, doc)
    other_project = uuid4()
    await db.execute(
        text(
            "INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency, created_at, updated_at) "
            "VALUES (:id, :t, 'P2', :code, 'construction', 'active', 'EUR', now(), now())"
        ),
        {"id": other_project, "t": w["tenant"], "code": f"p2-{other_project.hex[:6]}"},
    )
    await db.commit()
    await _enforce_with_grants(db, w, approver, READ, APPROVE, project=other_project)
    with pytest.raises(StructuredTrustForbidden) as denied:
        await _decide(test_session_factory, storage, w, receipt, "APPROVE", actor=approver)
    assert denied.value.code == "project_capability_required"
    assert (await _artifact(test_session_factory, receipt.artifact_id)).trust_state == "proposed"


async def test_a_rejection_does_not_need_the_revalidation_lock(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    """Rejecting never promotes anything, so a revocation never has to wait for it and it takes no grant lock at the end."""
    w, storage, approver, _doc, receipt, grants = await _setup(db, test_session_factory, tmp_path, READ, APPROVE)
    out = await _decide(test_session_factory, storage, w, receipt, "REJECT", actor=approver)
    assert out.trust_state == "rejected"
    await asyncio.wait_for(_revoke(test_session_factory, w, grants[APPROVE]), timeout=10)


@pytest.mark.parametrize("seed", range(10))
async def test_no_deadlock_between_approval_and_revocation_across_interleavings(
    db: AsyncSession, test_session_factory, tmp_path: Path, seed: int
) -> None:
    """Approval (document -> project -> review -> artifact -> grant FOR SHARE) against revocation (grant FOR UPDATE -> event).

    Whatever the interleaving, exactly one of two outcomes: promoted under the grant (revoked right after) or denied because
    the revocation won. Never a deadlock, never a hang, never a half state.
    """
    rng = random.Random(20261102 + seed)
    w, storage, approver, _doc, receipt, grants = await _setup(db, test_session_factory, tmp_path, READ, APPROVE)

    async def approve(delay: float) -> str:
        await asyncio.sleep(delay)
        try:
            await _decide(test_session_factory, storage, w, receipt, "APPROVE", actor=approver)
            return "promoted"
        except StructuredTrustForbidden:
            return "denied"

    async def revoke(delay: float) -> None:
        await asyncio.sleep(delay)
        await _revoke(test_session_factory, w, grants[APPROVE])

    verdict, _ = await asyncio.wait_for(
        asyncio.gather(approve(rng.uniform(0, 0.08)), revoke(rng.uniform(0, 0.08))), timeout=90
    )
    state = (await _artifact(test_session_factory, receipt.artifact_id)).trust_state
    assert state == ("trusted" if verdict == "promoted" else "proposed")
    assert await _decided_events(test_session_factory, w) == (1 if verdict == "promoted" else 0)
