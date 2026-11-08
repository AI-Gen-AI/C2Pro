"""SqlAlchemyCoherenceAlertCorrelationRunner over REAL PostgreSQL and the REAL ingestion worker.

The runner is a thin adapter over the single Coherence Alert mirror, so what matters here is the trust
behaviour end to end: the clause UUIDs come from the actual engine (``get_clauses_from_rag`` ->
``_evaluate``), the contract is actually uploaded and ingested, and nothing in the database or the mirror
is mocked.

* TRUSTED current contract: the Alert row carries ``source_clause_id`` and ``affected_entities.documents``
  of that contract; submitting the same alert again is idempotent and keeps a human disposition;
* PROPOSED contract, stale (superseded) revision, clause of another project or of another tenant: the
  alert is still recorded, but with no clause link and no document, so no false deep link can exist.

ProjectGraph itself seeds its signals with revision/artifact surrogate keys rather than persisted clause
UUIDs, so a positive link is only reachable here with the authentic engine alert.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.graph.project_graph import evaluate_artifact_set
from src.analysis.adapters.persistence.coherence_alert_correlation import (
    SqlAlchemyCoherenceAlertCorrelationRunner,
)
from src.analysis.adapters.persistence.risk_source_clause_binding import (
    load_trusted_risk_source_clause_ids,
)
from src.analysis.domain.contracts import DocumentArtifact, RiskItem
from src.coherence.router import get_clauses_from_rag
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.domain.models import DocumentType
from tests.integration.document_flow.test_budget_revision_authority_flow import (
    _propose,
    _reupload_and_ingest,
    _trust,
)
from tests.integration.document_flow.test_contract_revision_authority_flow import (
    _advisories,
    _contract_clause_ids,
    _contract_scenario,
    _other_contract,
)
from tests.integration.document_flow.test_contract_schedule_completion_flow import (
    LATE_SCHEDULE,
    PRICE_CLAUSE,
    PROVISIONAL_RULE,
    _project,
    _scenario,
    _upload_and_ingest,
    worker,  # noqa: F401  (pytest fixture)
)

pytestmark = pytest.mark.asyncio


async def _correlate(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    project_id: UUID,
    alerts: list[Any],
) -> dict[str, Any]:
    clauses = await get_clauses_from_rag(db, project_id, tenant_id)
    summary = await SqlAlchemyCoherenceAlertCorrelationRunner(
        db, project_id=project_id, tenant_id=tenant_id
    ).correlate(
        project_id=project_id,
        tenant_id=tenant_id,
        coherence_result=None,
        evaluation_alerts=alerts,
        source_clauses=clauses,
    )
    await db.commit()
    return dict(summary)


async def _rows(db: AsyncSession, project_id: UUID) -> list[Any]:
    result = await db.execute(
        text(
            "SELECT id, status::text AS status, resolution_notes, source_clause_id::text AS clause, "
            "affected_entities, alert_metadata->'detection_evidence' AS evidence "
            "FROM alerts WHERE project_id = :p AND rule_id = :r ORDER BY created_at, id"
        ),
        {"p": project_id, "r": PROVISIONAL_RULE},
    )
    return list(result.all())


def _assert_unlinked(row: Any, *foreign_documents: Any) -> None:
    assert row.clause is None
    documents = (row.affected_entities or {}).get("documents", [])
    for document in foreign_documents:
        assert str(document.id) not in documents
    assert documents == []
    assert (row.evidence or {}).get("source_document_id") is None


async def test_a_trusted_current_contract_links_the_alert_and_resubmission_is_idempotent(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id, contract, revision = await _contract_scenario(db, worker, test_user)
    await _propose(db, test_user, project_id, contract, revision)
    await _trust(db, test_user, project_id, contract, revision)
    [advisory] = await _advisories(db, test_user, project_id)
    clause_ids = await _contract_clause_ids(db, project_id, test_user, contract)
    assert advisory.evidence.source_clause_id in clause_ids

    summary = await _correlate(
        db, tenant_id=test_user.tenant_id, project_id=project_id, alerts=[advisory]
    )

    assert summary["alerts_submitted"] == 1 and summary["alerts_reconciled"] == 1
    assert summary["auto_resolve"] is False
    [row] = await _rows(db, project_id)
    assert row.clause == advisory.evidence.source_clause_id
    assert row.clause in clause_ids
    assert row.affected_entities["documents"] == [str(contract.id)]
    assert row.evidence["source_document_id"] == str(contract.id)

    # Identical resubmission: same row, same link, nothing new.
    await _correlate(db, tenant_id=test_user.tenant_id, project_id=project_id, alerts=[advisory])
    [again] = await _rows(db, project_id)
    assert again.id == row.id
    assert again.clause == row.clause
    assert again.affected_entities == row.affected_entities


async def test_a_human_disposition_survives_resubmission_of_the_same_alert(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id, contract, revision = await _contract_scenario(db, worker, test_user)
    await _trust(db, test_user, project_id, contract, revision)
    [advisory] = await _advisories(db, test_user, project_id)
    await _correlate(db, tenant_id=test_user.tenant_id, project_id=project_id, alerts=[advisory])
    [row] = await _rows(db, project_id)

    await db.execute(
        text(
            "UPDATE alerts SET status = 'dismissed', resolution_notes = 'reviewed by a human' "
            "WHERE id = :id"
        ),
        {"id": row.id},
    )
    await db.commit()

    await _correlate(db, tenant_id=test_user.tenant_id, project_id=project_id, alerts=[advisory])

    [after] = await _rows(db, project_id)
    assert after.id == row.id
    assert after.status.lower() == "dismissed"
    assert after.resolution_notes == "reviewed by a human"
    assert after.clause == row.clause


async def test_a_proposed_contract_does_not_link_an_alert_of_its_real_clause(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id, contract, revision = await _contract_scenario(db, worker, test_user)
    # Authentic engine alert on the real clause UUID, produced while the contract is still readable...
    [advisory] = await _advisories(db, test_user, project_id)
    assert advisory.evidence.source_clause_id in await _contract_clause_ids(
        db, project_id, test_user, contract
    )
    # ...then the contract only has a pending proposal: PROPOSED is not approved provenance.
    await _propose(db, test_user, project_id, contract, revision)

    await _correlate(db, tenant_id=test_user.tenant_id, project_id=project_id, alerts=[advisory])

    [row] = await _rows(db, project_id)
    _assert_unlinked(row, contract)


async def test_a_superseded_revision_clause_does_not_link_an_alert(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id, contract, revision = await _contract_scenario(db, worker, test_user)
    await _trust(db, test_user, project_id, contract, revision)
    [advisory] = await _advisories(db, test_user, project_id)
    stale_clause = advisory.evidence.source_clause_id

    revision_b = await _reupload_and_ingest(db, worker, test_user, contract, _other_contract())
    await _trust(db, test_user, project_id, contract, revision_b)
    assert stale_clause not in await _contract_clause_ids(db, project_id, test_user, contract)

    # The trust transition itself may have reconciled historical alerts. Isolate
    # fresh creation from stale input: previous alert records retain historical
    # lineage and must not be misclassified as newly-authorized source links.
    await db.execute(
        text("DELETE FROM alerts WHERE project_id = :p AND rule_id = :r"),
        {"p": project_id, "r": PROVISIONAL_RULE},
    )
    await db.commit()
    await _correlate(db, tenant_id=test_user.tenant_id, project_id=project_id, alerts=[advisory])

    [row] = await _rows(db, project_id)
    _assert_unlinked(row, contract)


async def test_a_clause_of_another_project_does_not_link_an_alert(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id, contract, revision = await _contract_scenario(db, worker, test_user)
    await _trust(db, test_user, project_id, contract, revision)
    [advisory] = await _advisories(db, test_user, project_id)

    other_project = await _project(db, test_user.tenant_id)
    await _correlate(
        db, tenant_id=test_user.tenant_id, project_id=other_project, alerts=[advisory]
    )

    [row] = await _rows(db, other_project)
    _assert_unlinked(row, contract)


async def test_a_clause_of_another_tenant_does_not_link_an_alert(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id, contract, revision = await _contract_scenario(db, worker, test_user)
    await _trust(db, test_user, project_id, contract, revision)
    [advisory] = await _advisories(db, test_user, project_id)

    foreign_tenant = uuid4()
    foreign_project = await _project(db, foreign_tenant)  # creates the tenant as well
    await _correlate(db, tenant_id=foreign_tenant, project_id=foreign_project, alerts=[advisory])

    [row] = await _rows(db, foreign_project)
    _assert_unlinked(row, contract)


async def test_a_mismatched_scope_is_refused_before_any_write(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id, _, _ = await _contract_scenario(db, worker, test_user)
    runner = SqlAlchemyCoherenceAlertCorrelationRunner(
        db, project_id=project_id, tenant_id=test_user.tenant_id
    )

    with pytest.raises(ValueError, match="ALERT_CORRELATION_SCOPE_MISMATCH"):
        await runner.correlate(
            project_id=uuid4(),
            tenant_id=test_user.tenant_id,
            coherence_result=None,
            evaluation_alerts=[object()],
            source_clauses=[],
        )
    assert await _rows(db, project_id) == []


PENALTY_CLAUSE = "7.3 Penalidades: el contratista abonara 500 euros por cada dia de retraso en la entrega final."
WARRANTY_CLAUSE = "9.1 Garantia: el contratista garantiza las obras durante veinticuatro meses."
PENALTY_REF = "7.3"
PENALTY_QUOTE = "500 euros por cada dia de retraso"


async def _bridge_alerts(
    db: AsyncSession, test_user: Any, project_id: UUID, contract: Any, revision: Any, *, quote: str
) -> tuple[Any, list[Any], dict[str, str]]:
    """Real N4 binding: persisted clause -> trusted loader mapping -> real engine alerts."""
    clauses = await SqlAlchemyDocumentRepository(db).list_clauses_bound_to_revision(
        test_user.tenant_id, contract.id, revision.revision_id
    )
    # The parser persists clause_code AUTO-NNN; the unique numbered heading is in full_text.
    [clause] = [c for c in clauses if (c.full_text or "").startswith(PENALTY_REF + " ")]
    assert clause.clause_code != PENALTY_REF and PENALTY_QUOTE in clause.full_text
    risk = RiskItem(
        title="Late delivery penalty",
        description="Daily penalty for late final delivery.",
        category="LEGAL",
        impact="HIGH",
        clause_ref=PENALTY_REF,
        source_quote=quote,
        source_quote_status="VERIFIED",
    )
    artifact = DocumentArtifact(
        document_id=str(contract.id),
        document_revision_id=str(revision.revision_id),
        doc_type="contract",
        extracted_risks=[risk],
    )
    mapping = await load_trusted_risk_source_clause_ids(
        db, tenant_id=test_user.tenant_id, project_id=project_id, artifacts=[artifact]
    )
    evaluation = await evaluate_artifact_set(
        [artifact],
        project_id=project_id,
        tenant_id=test_user.tenant_id,
        llm_on=False,
        risk_source_clause_ids=mapping,
    )
    return clause, list(evaluation.engine_result.alerts), mapping


async def _alert_rows(db: AsyncSession, project_id: UUID) -> list[Any]:
    result = await db.execute(
        text(
            "SELECT id, source_clause_id::text AS clause, affected_entities, "
            "alert_metadata->'detection_evidence' AS evidence "
            "FROM alerts WHERE project_id = :p ORDER BY created_at, id"
        ),
        {"p": project_id},
    )
    return list(result.all())


async def test_a_verified_n4_risk_binds_the_physical_trusted_clause_to_the_canonical_alert(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id, contract, revision, *_ = await _scenario(
        db, worker, test_user,
        contract=[PENALTY_CLAUSE, WARRANTY_CLAUSE, PRICE_CLAUSE],
        schedule=LATE_SCHEDULE,
    )
    await _propose(db, test_user, project_id, contract, revision)
    await _trust(db, test_user, project_id, contract, revision)

    clause, alerts, mapping = await _bridge_alerts(
        db, test_user, project_id, contract, revision, quote=PENALTY_QUOTE
    )
    assert list(mapping.values()) == [str(clause.id)]
    linked = [a for a in alerts if a.evidence.source_clause_id == str(clause.id)]
    assert linked, "the engine must emit an alert carrying the physical clause UUID"

    for _ in range(2):  # second pass proves idempotency
        await _correlate_with(db, test_user, project_id, alerts)
    rows = [r for r in await _alert_rows(db, project_id) if r.clause == str(clause.id)]
    assert len(rows) == len(linked)
    for row in rows:
        assert row.affected_entities["documents"] == [str(contract.id)]
        assert row.evidence["source_document_id"] == str(contract.id)
    assert len(await _alert_rows(db, project_id)) == len(alerts)


async def test_a_quote_from_another_clause_gets_no_verified_uuid_and_no_link(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id, contract, revision, *_ = await _scenario(
        db, worker, test_user,
        contract=[PENALTY_CLAUSE, WARRANTY_CLAUSE, PRICE_CLAUSE],
        schedule=LATE_SCHEDULE,
    )
    await _propose(db, test_user, project_id, contract, revision)
    await _trust(db, test_user, project_id, contract, revision)
    other_quote = "veinticuatro meses"

    clause, alerts, mapping = await _bridge_alerts(
        db, test_user, project_id, contract, revision, quote=other_quote
    )
    assert mapping == {}
    assert all(a.evidence.source_clause_id != str(clause.id) for a in alerts)

    await _correlate_with(db, test_user, project_id, alerts)
    assert all(r.clause is None for r in await _alert_rows(db, project_id))


async def _correlate_with(
    db: AsyncSession, test_user: Any, project_id: UUID, alerts: list[Any]
) -> None:
    await _correlate(db, tenant_id=test_user.tenant_id, project_id=project_id, alerts=alerts)
