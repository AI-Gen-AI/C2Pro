"""Lane C / C3b-1 -- governed, artifact-keyed materialization of an approved candidate.

TS-INT-C3B1-MAT-001. REAL PostgreSQL, the REAL #714 trust authority, the REAL
fenced HITL resume route and the REAL production graph nodes (the #646/#649/#714
harness).

Invariant under test: the same approved artifact may be delivered/retried any
number of times and canonical state changes AT MOST ONCE; a stale, superseded,
foreign or merely proposed artifact changes it NEVER.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.document_artifact_repository import (
    SqlAlchemyDocumentArtifactRepository,
)
from src.analysis.adapters.persistence.models import Alert, Analysis, DocumentArtifactORM
from src.analysis.application import trusted_materialization as materializer
from src.core.auth.models import Tenant, User
from src.core.tasks import materialization_tasks
from src.modules.hitl.domain.entities import ReviewStatus
from src.procurement.adapters.persistence.models import BOMItemORM
from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
from src.shared_kernel.enums import RACIRole
from src.stakeholders.adapters.persistence.models import StakeholderORM, StakeholderWBSRaciORM
from src.temporal.adapters.persistence.models import ProjectEventORM
from src.wbs.adapters.persistence.models import WBSNodeORM
from tests.modules.integration import test_issue714_trusted_state_commit as t714
from tests.modules.integration import test_p0b_crash_safe_resume_recovery as p0b
from tests.modules.integration.test_issue649_hitl_audit_idempotency import (
    _post_approve,
    request_sessions,  # noqa: F401 - pytest fixture
)
from tests.modules.integration.test_issue714_trusted_state_commit import (
    _binding,
    _commit_in,
    _propose,
    completion_sessions,  # noqa: F401 - pytest fixture
    graph_enqueues,  # noqa: F401 - pytest fixture
)
from tests.modules.integration.test_p0b_crash_safe_resume_recovery import (
    _arrange,
    independent_sessions,  # noqa: F401 - pytest fixture
    real_saver,  # noqa: F401 - pytest fixture
)

pytestmark = pytest.mark.asyncio


# ── helpers ──────────────────────────────────────────────────────────────────


async def _obligation(sessions, tenant_id: UUID, artifact_id: UUID) -> Any:
    async with sessions(tenant_id) as s:
        return (
            await s.execute(
                text(
                    "SELECT projection_state, materialization_state, materialized_analysis_id, "
                    "       materialization_detail, materialization_attempts "
                    "  FROM system_recovery.trusted_projection_index "
                    " WHERE artifact_id = cast(:a as uuid)"
                ),
                {"a": str(artifact_id)},
            )
        ).first()


async def _set_materialization(sessions, tenant_id: UUID, artifact_id: UUID, state: str) -> None:
    async with sessions(tenant_id) as s:
        await s.execute(
            text(
                "UPDATE system_recovery.trusted_projection_index "
                "SET materialization_state = :s WHERE artifact_id = cast(:a as uuid)"
            ),
            {"s": state, "a": str(artifact_id)},
        )


async def _analyses_for(sessions, tenant_id: UUID, artifact_id: UUID) -> list[Analysis]:
    async with sessions(tenant_id) as s:
        return list(
            (
                await s.execute(select(Analysis).where(Analysis.source_artifact_id == artifact_id))
            ).scalars()
        )


async def _project_counts(sessions, tenant_id: UUID, project_id: UUID) -> dict[str, int]:
    async with sessions(tenant_id) as s:

        async def count(model: Any) -> int:
            return int(
                await s.scalar(
                    select(func.count()).select_from(model).where(model.project_id == project_id)
                )
                or 0
            )

        events = int(
            await s.scalar(
                select(func.count())
                .select_from(ProjectEventORM)
                .where(
                    ProjectEventORM.project_id == project_id,
                    ProjectEventORM.event_type == materializer.MATERIALIZATION_COMPLETED_EVENT,
                )
            )
            or 0
        )
        return {
            "analyses": await count(Analysis),
            "alerts": await count(Alert),
            "wbs": await count(WBSNodeORM),
            "completed_events": events,
        }


def _worker(sessions):
    async def run(binding: Any, tenant_id: UUID) -> dict[str, Any]:
        return await materialization_tasks.materialize_pending_artifact(
            artifact_id=binding.artifact_id, tenant_id=tenant_id, session_factory=sessions
        )

    return run


async def _approved_but_unmaterialized(db, test_user, saver, register, sessions, completion):
    """An approval that committed trust and left its obligation pending.

    The trust authority is called directly (as any approval path other than
    the in-transaction resume would), so the durable obligation is exactly
    what the async materializer must drain.
    """
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register, with_candidate=False)
    await _propose(completion, arranged, tenant.id, title="Approved risk")
    binding = await _binding(db, arranged.review_row_id)
    assert binding is not None
    commit = await _commit_in(sessions, tenant.id, binding)
    assert commit.outcome.value == "committed"
    return tenant, arranged, binding


def _with_resumed_wbs(monkeypatch, wbs: list[dict[str, Any]]) -> None:
    initial_state = p0b._initial_state
    monkeypatch.setattr(
        p0b,
        "_initial_state",
        lambda *args, **kwargs: {
            **initial_state(*args, **kwargs),
            "extracted_risks": t714._risks("Resumed risk"),
            "extracted_wbs": wbs,
        },
    )


# ── 1. same artifact delivered twice / concurrently -> one materialization ───


async def test_same_artifact_delivered_repeatedly_materializes_once(
    real_saver,
    independent_sessions,
    completion_sessions,
    graph_enqueues,  # noqa: F811
    db: AsyncSession,
    test_user: User,
) -> None:
    saver, register = real_saver
    tenant, arranged, binding = await _approved_but_unmaterialized(
        db, test_user, saver, register, independent_sessions, completion_sessions
    )
    assert (
        await _obligation(independent_sessions, tenant.id, binding.artifact_id)
    ).materialization_state == "pending"
    run = _worker(independent_sessions)

    results = await asyncio.gather(*[run(binding, tenant.id) for _ in range(3)])
    results.append(await run(binding, tenant.id))

    statuses = sorted(r["status"] for r in results)
    assert statuses.count("created") == 1, statuses
    assert set(statuses) <= {"created", "noop"}
    [analysis] = await _analyses_for(independent_sessions, tenant.id, binding.artifact_id)
    obligation = await _obligation(independent_sessions, tenant.id, binding.artifact_id)
    assert obligation.materialization_state == "materialized"
    assert obligation.materialized_analysis_id == analysis.id
    counts = await _project_counts(independent_sessions, tenant.id, arranged.project_id)
    assert counts["analyses"] == 1 and counts["completed_events"] == 1
    assert counts["alerts"] == len(t714._risks("Approved risk"))


# ── 2. synchronous resume + async replay -> ONE canonical effect ─────────────


async def test_sync_resume_plus_async_replay_is_one_canonical_effect(
    real_saver,
    independent_sessions,
    request_sessions,
    completion_sessions,  # noqa: F811
    graph_enqueues,
    db: AsyncSession,
    test_user: User,  # noqa: F811
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register, with_candidate=False)
    await _propose(completion_sessions, arranged, tenant.id, title="Reviewed risk")
    binding = await _binding(db, arranged.review_row_id)

    response = await _post_approve(
        request_sessions,
        tenant.id,
        arranged.review_item_id,
        saver=saver,
        app=arranged.app,
        sessions=independent_sessions,
    )
    assert response.current_status == ReviewStatus.APPROVED

    # The approval transaction itself materialized: nothing is left pending.
    [analysis] = await _analyses_for(independent_sessions, tenant.id, binding.artifact_id)
    assert analysis.resume_operation_id is not None
    obligation = await _obligation(independent_sessions, tenant.id, binding.artifact_id)
    assert obligation.materialization_state == "materialized"
    assert obligation.materialized_analysis_id == analysis.id
    before = await _project_counts(independent_sessions, tenant.id, arranged.project_id)
    assert before["analyses"] == 1 and before["completed_events"] == 1

    run = _worker(independent_sessions)
    assert (await run(binding, tenant.id))["status"] == "noop"
    # Even a delivery that finds the obligation pending again (lost ack, manual
    # requeue) only re-links the existing result.
    await _set_materialization(independent_sessions, tenant.id, binding.artifact_id, "pending")
    replay = await run(binding, tenant.id)
    assert replay["status"] == "already_materialized"
    assert replay["analysis_id"] == str(analysis.id)

    assert await _project_counts(independent_sessions, tenant.id, arranged.project_id) == before
    assert (
        await _obligation(independent_sessions, tenant.id, binding.artifact_id)
    ).materialization_state == "materialized"


# ── 3. a pending obligation survives broker loss ─────────────────────────────


async def test_pending_obligation_survives_broker_loss(
    real_saver,
    independent_sessions,
    completion_sessions,
    graph_enqueues,  # noqa: F811
    db: AsyncSession,
    test_user: User,
    monkeypatch,
) -> None:
    saver, register = real_saver
    tenant, arranged, binding = await _approved_but_unmaterialized(
        db, test_user, saver, register, independent_sessions, completion_sessions
    )
    dispatched: list[UUID] = []
    monkeypatch.setattr(
        materialization_tasks,
        "enqueue_materialization",
        lambda *, artifact_id, tenant_id: dispatched.append(artifact_id),
    )

    # No fast path ever ran (the broker lost it). The beat sweep finds it.
    await materialization_tasks.reconcile_pending_materializations(
        grace_seconds=0, session_factory=lambda: independent_sessions(tenant.id)
    )
    assert binding.artifact_id in dispatched
    assert (
        await _obligation(independent_sessions, tenant.id, binding.artifact_id)
    ).materialization_state == "pending"

    assert (await _worker(independent_sessions)(binding, tenant.id))["status"] == "created"
    assert len(await _analyses_for(independent_sessions, tenant.id, binding.artifact_id)) == 1


# ── 4. V3 supersedes V2 before V2's materializer takes its lock ──────────────


async def test_superseded_v2_materialization_writes_nothing(
    real_saver,
    independent_sessions,
    completion_sessions,
    graph_enqueues,  # noqa: F811
    db: AsyncSession,
    test_user: User,
) -> None:
    saver, register = real_saver
    tenant, arranged, v2 = await _approved_but_unmaterialized(
        db, test_user, saver, register, independent_sessions, completion_sessions
    )
    # A newer version of the same document becomes trusted before V2 drains.
    await _propose(completion_sessions, arranged, tenant.id, title="V3 risk")
    v3 = await _binding_for_latest(independent_sessions, tenant.id, arranged.document_id)
    await _commit_in(independent_sessions, tenant.id, v3)

    v2_obligation = await _obligation(independent_sessions, tenant.id, v2.artifact_id)
    assert v2_obligation.materialization_state == "obsolete"
    # Even if a delivery still sees V2 as pending, the stale guard refuses it.
    await _set_materialization(independent_sessions, tenant.id, v2.artifact_id, "pending")
    result = await _worker(independent_sessions)(v2, tenant.id)
    assert result["status"] == "obsolete"
    assert result["reason"].startswith("artifact_not_trusted_active")
    assert await _analyses_for(independent_sessions, tenant.id, v2.artifact_id) == []
    assert (await _project_counts(independent_sessions, tenant.id, arranged.project_id))[
        "analyses"
    ] == 0

    # V3 -- the trusted-current artifact -- materializes; V3 is never overwritten.
    assert (await _worker(independent_sessions)(v3, tenant.id))["status"] == "created"
    assert len(await _analyses_for(independent_sessions, tenant.id, v3.artifact_id)) == 1


async def _binding_for_latest(sessions, tenant_id: UUID, document_id: UUID) -> Any:
    from src.analysis.domain.trust import CandidateBinding

    rows = await t714._rows(sessions, tenant_id, document_id)
    latest = rows[-1]
    return CandidateBinding(
        artifact_id=latest.artifact_id,
        document_id=latest.document_id,
        artifact_version=int(latest.artifact_version),
        artifact_hash=str(latest.artifact_hash),
    )


# ── 5. unknown / stale binding -> zero writes ────────────────────────────────


async def test_stale_or_unknown_binding_writes_nothing(
    real_saver,
    independent_sessions,
    completion_sessions,
    graph_enqueues,  # noqa: F811
    db: AsyncSession,
    test_user: User,
) -> None:
    saver, register = real_saver
    tenant, arranged, binding = await _approved_but_unmaterialized(
        db, test_user, saver, register, independent_sessions, completion_sessions
    )
    async with independent_sessions(tenant.id) as s:
        await s.execute(
            text(
                "UPDATE system_recovery.trusted_projection_index SET artifact_hash = :h "
                "WHERE artifact_id = cast(:a as uuid)"
            ),
            {"h": "f" * 64, "a": str(binding.artifact_id)},
        )
    result = await _worker(independent_sessions)(binding, tenant.id)
    assert (result["status"], result["reason"]) == ("obsolete", "binding_mismatch")

    unknown = await materialization_tasks.materialize_pending_artifact(
        artifact_id=uuid4(), tenant_id=tenant.id, session_factory=independent_sessions
    )
    assert unknown["status"] == "no_obligation"
    assert await _project_counts(independent_sessions, tenant.id, arranged.project_id) == {
        "analyses": 0,
        "alerts": 0,
        "wbs": 0,
        "completed_events": 0,
    }


# ── 6. artifact from the wrong tenant / project / document -> zero writes ────


async def test_foreign_scope_writes_nothing(
    real_saver,
    independent_sessions,
    completion_sessions,
    graph_enqueues,  # noqa: F811
    db: AsyncSession,
    test_user: User,
) -> None:
    saver, register = real_saver
    tenant, arranged, binding = await _approved_but_unmaterialized(
        db, test_user, saver, register, independent_sessions, completion_sessions
    )
    exact = materializer.ArtifactRef(
        artifact_id=binding.artifact_id,
        document_id=binding.document_id,
        artifact_version=binding.artifact_version,
        artifact_hash=binding.artifact_hash,
        project_id=arranged.project_id,
        tenant_id=tenant.id,
    )
    content = materializer.MaterializationContent(document_id=None, risks=[], wbs=[])
    cases = {
        "artifact_scope_mismatch": [
            {"project_id": uuid4()},
            {"document_id": uuid4()},
        ],
        "artifact_not_found": [{"tenant_id": uuid4()}],
    }
    for reason, overrides in cases.items():
        for override in overrides:
            ref = materializer.ArtifactRef(**{**exact.__dict__, **override})
            async with independent_sessions(ref.tenant_id) as s:
                outcome = await materializer.materialize_in_transaction(s, ref=ref, content=content)
            assert (outcome.status, outcome.reason) == (
                materializer.MaterializationStatus.OBSOLETE,
                reason,
            ), override
    assert await _project_counts(independent_sessions, tenant.id, arranged.project_id) == {
        "analyses": 0,
        "alerts": 0,
        "wbs": 0,
        "completed_events": 0,
    }


# ── 7. projection obligation semantics stay independent ──────────────────────


async def test_projection_obligation_is_independent_of_materialization(
    real_saver,
    independent_sessions,
    completion_sessions,
    graph_enqueues,  # noqa: F811
    db: AsyncSession,
    test_user: User,
) -> None:
    saver, register = real_saver
    tenant, arranged, binding = await _approved_but_unmaterialized(
        db, test_user, saver, register, independent_sessions, completion_sessions
    )
    row = await _obligation(independent_sessions, tenant.id, binding.artifact_id)
    assert (row.projection_state, row.materialization_state) == ("pending", "pending")

    await _worker(independent_sessions)(binding, tenant.id)
    row = await _obligation(independent_sessions, tenant.id, binding.artifact_id)
    # Materializing never acknowledges the ProjectGraph projection...
    assert (row.projection_state, row.materialization_state) == ("pending", "materialized")

    # ...and the ProjectGraph acknowledgement never touches materialization.
    async with independent_sessions(tenant.id) as s:
        repo = SqlAlchemyDocumentArtifactRepository(s)
        await repo.list_trusted_for_project(project_id=arranged.project_id, tenant_id=tenant.id)
        assert (
            await repo.mark_loaded_projected(project_id=arranged.project_id, tenant_id=tenant.id)
            == 1
        )
    row = await _obligation(independent_sessions, tenant.id, binding.artifact_id)
    assert (row.projection_state, row.materialization_state) == ("projected", "materialized")


# ── 8. historical / non-gated obligations never auto-materialize ─────────────


async def test_historical_and_non_gated_obligations_are_never_scheduled(
    real_saver,
    independent_sessions,
    completion_sessions,
    graph_enqueues,  # noqa: F811
    db: AsyncSession,
    test_user: User,
    monkeypatch,
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register, with_candidate=False)
    # Non-gated TRUSTED completion: materialized in-graph by its own N17.
    await t714._seed_trusted(independent_sessions, arranged, tenant.id, "Non-gated risk")
    [trusted] = await t714._rows(independent_sessions, tenant.id, arranged.document_id)
    # A pre-C3b obligation row, written exactly as the 0714 code wrote it.
    historical = DocumentArtifactORM(
        artifact_id=uuid4(),
        document_id=uuid4(),
        project_id=arranged.project_id,
        tenant_id=tenant.id,
        payload={"document_id": "x", "doc_type": "contract"},
        lifecycle_status="active",
        artifact_version=1,
        artifact_hash="a" * 64,
        trust_state="trusted",
    )
    async with independent_sessions(tenant.id) as s:
        s.add(historical)
        await s.flush()
        await s.execute(
            text(
                "INSERT INTO system_recovery.trusted_projection_index (artifact_id, document_id, "
                "project_id, tenant_id, artifact_version, artifact_hash, projection_state) "
                "VALUES (:a, :d, :p, :t, 1, :h, 'projected')"
            ),
            {
                "a": historical.artifact_id,
                "d": historical.document_id,
                "p": arranged.project_id,
                "t": tenant.id,
                "h": "a" * 64,
            },
        )

    for artifact_id in (trusted.artifact_id, historical.artifact_id):
        assert (
            await _obligation(independent_sessions, tenant.id, artifact_id)
        ).materialization_state == "not_required"

    dispatched: list[UUID] = []
    monkeypatch.setattr(
        materialization_tasks,
        "enqueue_materialization",
        lambda *, artifact_id, tenant_id: dispatched.append(artifact_id),
    )
    await materialization_tasks.reconcile_pending_materializations(
        grace_seconds=0, session_factory=lambda: independent_sessions(tenant.id)
    )
    assert trusted.artifact_id not in dispatched and historical.artifact_id not in dispatched
    for artifact_id in (trusted.artifact_id, historical.artifact_id):
        result = await materialization_tasks.materialize_pending_artifact(
            artifact_id=artifact_id, tenant_id=tenant.id, session_factory=independent_sessions
        )
        assert result == {"status": "noop", "materialization_state": "not_required"}
    assert (await _project_counts(independent_sessions, tenant.id, arranged.project_id))[
        "analyses"
    ] == 0


# ── 9 / 10. generated WBS codes are not identity; canonical WBS is preserved ──


async def _canonical_wbs_with_relationships(db: AsyncSession, tenant_id: UUID, project_id: UUID):
    [node] = await SQLAlchemyWBSRepository(db).bulk_create_from_dicts(
        project_id, [{"code": "1", "name": "Civil works (approved baseline)"}], tenant_id
    )
    await db.commit()
    stakeholder = StakeholderORM(id=uuid4(), tenant_id=tenant_id, project_id=project_id, name="PM")
    db.add(stakeholder)
    await db.flush()
    db.add_all(
        [
            StakeholderWBSRaciORM(
                tenant_id=tenant_id,
                project_id=project_id,
                stakeholder_id=stakeholder.id,
                wbs_item_id=node.id,
                raci_role=RACIRole.ACCOUNTABLE,
                generated_automatically=False,
                manually_verified=True,
            ),
            BOMItemORM(
                id=uuid4(),
                project_id=project_id,
                item_name="Concrete",
                quantity=Decimal("10"),
                wbs_item_id=node.id,
            ),
        ]
    )
    await db.commit()
    return node.id


async def test_generated_wbs_code_never_replaces_or_relinks_canonical_wbs(
    real_saver,
    independent_sessions,
    request_sessions,
    completion_sessions,  # noqa: F811
    graph_enqueues,
    db: AsyncSession,
    test_user: User,
    monkeypatch,  # noqa: F811
) -> None:
    # The approved run proposes a node with the SAME generated code "1" but a
    # different meaning, plus a new one. Same code must not mean same entity.
    _with_resumed_wbs(
        monkeypatch,
        [{"code": "1", "name": "Electrical works (AI V2)"}, {"code": "2", "name": "New"}],
    )
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register, with_candidate=False)
    node_id = await _canonical_wbs_with_relationships(db, tenant.id, arranged.project_id)
    await _propose(completion_sessions, arranged, tenant.id, title="Reviewed risk")
    binding = await _binding(db, arranged.review_row_id)

    await _post_approve(
        request_sessions,
        tenant.id,
        arranged.review_item_id,
        saver=saver,
        app=arranged.app,
        sessions=independent_sessions,
    )

    async with independent_sessions(tenant.id) as s:
        nodes = (
            await s.execute(
                select(WBSNodeORM.id, WBSNodeORM.code, WBSNodeORM.name).where(
                    WBSNodeORM.project_id == arranged.project_id
                )
            )
        ).all()
        raci = (
            (
                await s.execute(
                    select(StakeholderWBSRaciORM).where(
                        StakeholderWBSRaciORM.project_id == arranged.project_id
                    )
                )
            )
            .scalars()
            .all()
        )
        bom = (
            await s.execute(select(BOMItemORM).where(BOMItemORM.project_id == arranged.project_id))
        ).scalar_one()
    assert [(n.id, n.code, n.name) for n in nodes] == [
        (node_id, "1", "Civil works (approved baseline)")
    ]
    assert [(r.wbs_item_id, r.manually_verified) for r in raci] == [(node_id, True)]
    assert bom.wbs_item_id == node_id
    obligation = await _obligation(independent_sessions, tenant.id, binding.artifact_id)
    assert obligation.materialization_state == "materialized"
    assert (
        materializer.MaterializationQualification.WBS_RECONCILIATION_REQUIRED
        in obligation.materialization_detail["qualifications"]
    )
    # The approved analysis itself is durable; only the WBS effect is deferred.
    assert len(await _analyses_for(independent_sessions, tenant.id, binding.artifact_id)) == 1


async def test_project_without_canonical_wbs_receives_the_approved_wbs(
    real_saver,
    independent_sessions,
    request_sessions,
    completion_sessions,  # noqa: F811
    graph_enqueues,
    db: AsyncSession,
    test_user: User,
    monkeypatch,  # noqa: F811
) -> None:
    _with_resumed_wbs(monkeypatch, [{"code": "1", "name": "Civil works"}])
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register, with_candidate=False)
    await _propose(completion_sessions, arranged, tenant.id, title="Reviewed risk")
    binding = await _binding(db, arranged.review_row_id)

    await _post_approve(
        request_sessions,
        tenant.id,
        arranged.review_item_id,
        saver=saver,
        app=arranged.app,
        sessions=independent_sessions,
    )

    counts = await _project_counts(independent_sessions, tenant.id, arranged.project_id)
    assert counts["wbs"] == 1
    obligation = await _obligation(independent_sessions, tenant.id, binding.artifact_id)
    assert (
        materializer.MaterializationQualification.WBS_RECONCILIATION_REQUIRED
        not in obligation.materialization_detail["qualifications"]
    )


# ── 11. alerts: no second identity system; reconciliation waits on #828 ──────


async def test_alert_identity_is_not_duplicated_and_waits_on_828(
    real_saver,
    independent_sessions,
    completion_sessions,
    graph_enqueues,  # noqa: F811
    db: AsyncSession,
    test_user: User,
) -> None:
    saver, register = real_saver
    tenant, arranged, binding = await _approved_but_unmaterialized(
        db, test_user, saver, register, independent_sessions, completion_sessions
    )
    await _worker(independent_sessions)(binding, tenant.id)

    async with independent_sessions(tenant.id) as s:
        alert_columns = set(
            (
                await s.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' AND table_name = 'alerts'"
                    )
                )
            ).scalars()
        )
    assert "fingerprint" not in alert_columns
    [analysis] = await _analyses_for(independent_sessions, tenant.id, binding.artifact_id)
    async with independent_sessions(tenant.id) as s:
        linked = await s.scalar(
            select(func.count()).select_from(Alert).where(Alert.analysis_id == analysis.id)
        )
    assert linked == len(t714._risks("Approved risk"))
    obligation = await _obligation(independent_sessions, tenant.id, binding.artifact_id)
    assert obligation.materialization_detail["qualifications"] == [
        materializer.MaterializationQualification.ALERT_RECONCILIATION_WAITING_ON_828
    ]


# ── 12. a PROPOSED revision performs zero canonical writes ───────────────────


async def test_proposed_revision_performs_zero_canonical_writes(
    real_saver,
    independent_sessions,
    completion_sessions,
    graph_enqueues,  # noqa: F811
    db: AsyncSession,
    test_user: User,
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register, with_candidate=False)
    await _propose(completion_sessions, arranged, tenant.id, title="Pending risk")
    binding = await _binding(db, arranged.review_row_id)

    assert await _obligation(independent_sessions, tenant.id, binding.artifact_id) is None
    result = await _worker(independent_sessions)(binding, tenant.id)
    assert result == {"status": "no_obligation"}
    # Even the materializer itself refuses a PROPOSED artifact.
    async with independent_sessions(tenant.id) as s:
        outcome = await materializer.materialize_in_transaction(
            s,
            ref=materializer.ArtifactRef(
                artifact_id=binding.artifact_id,
                document_id=binding.document_id,
                artifact_version=binding.artifact_version,
                artifact_hash=binding.artifact_hash,
                project_id=arranged.project_id,
                tenant_id=tenant.id,
            ),
            content=materializer.MaterializationContent(
                document_id=None, risks=t714._risks("x"), wbs=[{"code": "1", "name": "n"}]
            ),
        )
    assert outcome.status is materializer.MaterializationStatus.OBSOLETE
    assert outcome.reason == "artifact_not_trusted_active:proposed/active"
    assert await _project_counts(independent_sessions, tenant.id, arranged.project_id) == {
        "analyses": 0,
        "alerts": 0,
        "wbs": 0,
        "completed_events": 0,
    }


# ── 14. analyses.source_artifact_id is DB-enforced ───────────────────────────


async def test_source_artifact_identity_is_enforced_by_the_database(
    real_saver,
    independent_sessions,
    completion_sessions,
    graph_enqueues,  # noqa: F811
    db: AsyncSession,
    test_user: User,
) -> None:
    saver, register = real_saver
    tenant, arranged, binding = await _approved_but_unmaterialized(
        db, test_user, saver, register, independent_sessions, completion_sessions
    )

    def _analysis(project_id: UUID) -> Analysis:
        return Analysis(
            id=uuid4(),
            tenant_id=tenant.id,
            project_id=project_id,
            source_artifact_id=binding.artifact_id,
            alerts_count=0,
        )

    # An analysis in ANOTHER project attributed to this project's artifact.
    other_project = uuid4()
    async with independent_sessions(tenant.id) as s:
        await s.execute(
            text(
                "INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency, "
                "created_at, updated_at) VALUES (:id, :tid, 'other', :code, 'construction', "
                "'active', 'EUR', now(), now())"
            ),
            {"id": other_project, "tid": tenant.id, "code": f"P-{other_project.hex[:8]}"},
        )
    with pytest.raises(IntegrityError, match="fk_analyses_source_artifact_scope"):
        async with independent_sessions(tenant.id) as s:
            s.add(_analysis(other_project))
            await s.flush()

    # A second materialization of the same artifact.
    await _worker(independent_sessions)(binding, tenant.id)
    with pytest.raises(IntegrityError, match="uq_analyses_source_artifact"):
        async with independent_sessions(tenant.id) as s:
            s.add(_analysis(arranged.project_id))
            await s.flush()


# ── crash windows ────────────────────────────────────────────────────────────


async def test_crash_mid_materialization_rolls_back_and_the_retry_completes(
    real_saver,
    independent_sessions,
    completion_sessions,
    graph_enqueues,  # noqa: F811
    db: AsyncSession,
    test_user: User,
    monkeypatch,
) -> None:
    saver, register = real_saver
    tenant, arranged, binding = await _approved_but_unmaterialized(
        db, test_user, saver, register, independent_sessions, completion_sessions
    )
    real_mark = materializer._mark_materialized

    async def _crash(*_: Any, **__: Any) -> None:
        raise RuntimeError("process lost after every canonical write, before completion")

    monkeypatch.setattr(materializer, "_mark_materialized", _crash)
    result = await _worker(independent_sessions)(binding, tenant.id)
    assert result == {"status": "failed", "materialization_state": "pending"}
    assert await _project_counts(independent_sessions, tenant.id, arranged.project_id) == {
        "analyses": 0,
        "alerts": 0,
        "wbs": 0,
        "completed_events": 0,
    }
    assert (
        await _obligation(independent_sessions, tenant.id, binding.artifact_id)
    ).materialization_attempts == 1

    monkeypatch.setattr(materializer, "_mark_materialized", real_mark)
    assert (await _worker(independent_sessions)(binding, tenant.id))["status"] == "created"
    assert len(await _analyses_for(independent_sessions, tenant.id, binding.artifact_id)) == 1


async def test_repeated_failure_stops_at_operator_required_without_touching_trust(
    real_saver,
    independent_sessions,
    completion_sessions,
    graph_enqueues,  # noqa: F811
    db: AsyncSession,
    test_user: User,
    monkeypatch,
) -> None:
    saver, register = real_saver
    tenant, arranged, binding = await _approved_but_unmaterialized(
        db, test_user, saver, register, independent_sessions, completion_sessions
    )

    async def _boom(*_: Any, **__: Any) -> None:
        raise RuntimeError("persistent failure")

    monkeypatch.setattr(materializer, "_mark_materialized", _boom)
    states = [
        (await _worker(independent_sessions)(binding, tenant.id))["materialization_state"]
        for _ in range(materialization_tasks.MAX_MATERIALIZATION_ATTEMPTS)
    ]
    assert states[-1] == "operator_required"
    assert set(states[:-1]) == {"pending"}
    rows = await t714._rows(independent_sessions, tenant.id, arranged.document_id)
    assert [(r.trust_state, r.lifecycle_status) for r in rows] == [("trusted", "active")]
    assert (await _project_counts(independent_sessions, tenant.id, arranged.project_id))[
        "analyses"
    ] == 0
