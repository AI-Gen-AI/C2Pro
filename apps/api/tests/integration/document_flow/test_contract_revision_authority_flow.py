"""A contract that awaits approval is not canonical input (#1133, same rule as the budget side of #1108).

REAL PostgreSQL and the REAL ingestion worker. The contract side of the coherence reading (the stated
total, its currencies, the clauses the rules and the completion-deadline comparison read) used the
``resolved`` flag alone, so a single-revision contract whose only artifact is a pending PROPOSAL fed
canonical findings, while the link from the finding back to its clause (#1111) already required TRUSTED.
One definition now covers both: the contract is canonical input when it is TRUSTED, or when no proposal
for it is pending (no artifact at all is the pre-HITL state of a plain upload and keeps working).

* contract with a pending proposal (bound to the revision, or unbound): no total, no currency, no clause,
  no completion-deadline finding;
* contract with no artifact: still read, but its alert has no ``source_clause_id`` (fail closed, #1111);
* contract approved: read and linked;
* a pending proposal of another contract, another project or another tenant changes nothing.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.coherence.budget_clause_builder import _CONTRACT_CURRENCIES_SQL, load_contract_total
from src.coherence.router import (
    _get_parsed_text_fallback_clauses,
    _get_rag_chunk_clauses,
    _mirror_coherence_alerts_to_alerts_table,
    get_clauses_from_rag,
)
from src.documents.domain.models import DocumentType
from tests.integration.document_flow.test_budget_revision_authority_flow import _propose, _trust
from tests.integration.document_flow.test_contract_schedule_completion_flow import (
    COMPLETION_CLAUSE,
    LATE_SCHEDULE,
    PRICE_CLAUSE,
    PROVISIONAL_RULE,
    _evaluate,
    _project,
    _scenario,
    _upload_and_ingest,
    worker,  # noqa: F401  (pytest fixture)
)

pytestmark = pytest.mark.asyncio

TOTAL = 1_000_000.0


async def _contract_scenario(db: AsyncSession, worker: Any, user: Any) -> tuple[UUID, Any, Any]:
    project_id, contract, revision, *_ = await _scenario(
        db, worker, user, contract=[PRICE_CLAUSE, COMPLETION_CLAUSE], schedule=LATE_SCHEDULE
    )
    return project_id, contract, revision


async def _contract_clause_ids(
    db: AsyncSession, project_id: UUID, user: Any, contract: Any
) -> list[str]:
    clauses = await get_clauses_from_rag(db, project_id, user.tenant_id)
    return [c.id for c in clauses if c.data.get("document_id") == str(contract.id)]


async def _advisories(db: AsyncSession, user: Any, project_id: UUID) -> list[Any]:
    result = await _evaluate(db, user, project_id)
    return [a for a in result.alerts if a.rule_id == PROVISIONAL_RULE]


async def test_a_contract_with_a_pending_proposal_is_not_canonical_input(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id, contract, revision = await _contract_scenario(db, worker, test_user)
    await _propose(db, test_user, project_id, contract, revision)

    assert await load_contract_total(db, project_id, test_user.tenant_id) is None
    assert await _contract_clause_ids(db, project_id, test_user, contract) == []
    assert await _advisories(db, test_user, project_id) == []


async def test_an_unbound_pending_proposal_of_a_single_revision_contract_is_still_pending(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id, contract, revision = await _contract_scenario(db, worker, test_user)
    await _propose(db, test_user, project_id, contract, revision)
    await db.execute(
        text("UPDATE document_artifacts SET document_revision_id = NULL WHERE document_id = :d"),
        {"d": contract.id},
    )
    await db.commit()

    assert await load_contract_total(db, project_id, test_user.tenant_id) is None
    assert await _contract_clause_ids(db, project_id, test_user, contract) == []


async def test_a_contract_without_any_artifact_is_read_but_its_alert_has_no_source_link(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    """The pre-approval state of a plain upload keeps feeding the reading, and fails closed on provenance."""
    project_id, contract, _ = await _contract_scenario(db, worker, test_user)

    assert await load_contract_total(db, project_id, test_user.tenant_id) == TOTAL
    [advisory] = await _advisories(db, test_user, project_id)
    clauses = await get_clauses_from_rag(db, project_id, test_user.tenant_id)
    await _mirror_coherence_alerts_to_alerts_table(
        db=db,
        project_id=project_id,
        tenant_id=test_user.tenant_id,
        alerts=[advisory],
        clauses=clauses,
    )
    await db.commit()

    row = (
        await db.execute(
            text(
                "SELECT source_clause_id::text AS clause, affected_entities "
                "FROM alerts WHERE project_id = :p AND rule_id = :r"
            ),
            {"p": project_id, "r": PROVISIONAL_RULE},
        )
    ).one()
    assert row.clause is None
    assert str(contract.id) not in (row.affected_entities or {}).get("documents", [])


async def test_an_approved_contract_is_read_and_its_alert_is_linked(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id, contract, revision = await _contract_scenario(db, worker, test_user)
    await _propose(db, test_user, project_id, contract, revision)
    await _trust(db, test_user, project_id, contract, revision)  # approval supersedes the proposal

    assert await load_contract_total(db, project_id, test_user.tenant_id) == TOTAL
    [advisory] = await _advisories(db, test_user, project_id)
    assert advisory.evidence.source_clause_id in await _contract_clause_ids(
        db, project_id, test_user, contract
    )


async def test_a_pending_proposal_of_another_project_changes_nothing(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id, contract, _ = await _contract_scenario(db, worker, test_user)
    other_project = await _project(db, test_user.tenant_id)
    other, other_revision = await _upload_and_ingest(
        db,
        worker,
        test_user,
        other_project,
        filename="other.docx",
        content=_other_contract(),
        document_type=DocumentType.CONTRACT,
    )
    await _propose(db, test_user, other_project, other, other_revision)

    assert await load_contract_total(db, project_id, test_user.tenant_id) == TOTAL
    assert await _contract_clause_ids(db, project_id, test_user, contract) != []


async def _currencies(db: AsyncSession, project_id: UUID, user: Any) -> list[str] | None:
    row = await db.execute(
        _CONTRACT_CURRENCIES_SQL, {"project_id": str(project_id), "tenant_id": str(user.tenant_id)}
    )
    return row.scalar_one_or_none()


async def _state_a_currency(db: AsyncSession, contract: Any) -> None:
    await db.execute(
        text(
            "UPDATE clauses SET extracted_entities = extracted_entities || "
            '\'{"currency": "USD", "currency_source": "explicit", "total_amount": 1}\'::jsonb '
            "WHERE document_id = :d"
        ),
        {"d": contract.id},
    )
    await db.commit()


async def test_a_pending_contract_contributes_no_currency(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id, contract, revision = await _contract_scenario(db, worker, test_user)
    await _state_a_currency(db, contract)
    assert await _currencies(db, project_id, test_user) == [
        "USD"
    ]  # pre-approval upload keeps feeding

    await _propose(db, test_user, project_id, contract, revision)

    assert await _currencies(db, project_id, test_user) is None


async def test_the_parsed_text_fallback_does_not_read_a_pending_contract(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id, contract, revision = await _contract_scenario(db, worker, test_user)

    def of_contract(clauses: list[Any]) -> list[Any]:
        return [c for c in clauses if c.data.get("document_id") == str(contract.id)]

    read = await _get_parsed_text_fallback_clauses(db, project_id, test_user.tenant_id)
    assert of_contract(read) != []  # the source is reachable before the proposal

    await _propose(db, test_user, project_id, contract, revision)

    read = await _get_parsed_text_fallback_clauses(db, project_id, test_user.tenant_id)
    assert of_contract(read) == []


async def test_only_the_contract_carries_the_pending_proposal_rule(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id, _, _ = await _contract_scenario(db, worker, test_user)
    specification, revision = await _upload_and_ingest(
        db,
        worker,
        test_user,
        project_id,
        filename="spec.docx",
        content=_other_contract(),
        document_type=DocumentType.SPECIFICATION,
    )
    await _propose(db, test_user, project_id, specification, revision)

    chunks = await _get_rag_chunk_clauses(db, project_id, test_user.tenant_id, max_chunks=50)
    assert [c for c in chunks if c.data.get("document_id") == str(specification.id)] != []


async def test_a_legacy_trusted_artifact_without_a_binding_stays_canonical_when_a_reanalysis_is_proposed(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id, contract, revision = await _contract_scenario(db, worker, test_user)
    await _trust(db, test_user, project_id, contract, revision)
    await db.execute(
        text("UPDATE document_artifacts SET document_revision_id = NULL WHERE document_id = :d"),
        {"d": contract.id},
    )
    await db.commit()
    await _propose(db, test_user, project_id, contract, revision)

    assert await load_contract_total(db, project_id, test_user.tenant_id) == TOTAL


def _other_contract() -> bytes:
    from tests.integration.document_flow.test_contract_schedule_completion_flow import _docx

    return _docx([PRICE_CLAUSE])
