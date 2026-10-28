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
    _documents_excluded_from_evaluation,
    _get_parsed_text_fallback_clauses,
    _get_rag_chunk_clauses,
    _mirror_coherence_alerts_to_alerts_table,
    get_clauses_from_rag,
)
from src.documents.adapters.persistence.models import DocumentORM
from src.documents.domain.models import DocumentType
from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)
from tests.integration.document_flow.test_budget_revision_authority_flow import (
    _propose,
    _reupload_and_ingest,
    _trust,
)
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


# ── "not evaluated" is never "resolved" ───────────────────────────────────────────────────────────────


async def _alert_row(db: AsyncSession, project_id: UUID) -> dict[str, Any]:
    row = (
        await db.execute(
            text(
                "SELECT status::text AS status, resolved_at, resolution_notes, title, severity::text AS severity, "
                "rule_id, alert_metadata->>'fingerprint' AS fingerprint "
                "FROM alerts WHERE project_id = :p AND rule_id = :r"
            ),
            {"p": project_id, "r": PROVISIONAL_RULE},
        )
    ).one()
    return dict(row._mapping)


OBJECT_CLAUSE = "Objeto. El contratista ejecutará las obras de urbanización descritas en el proyecto de referencia."
PENALTY_CLAUSE = "Penalizaciones. El retraso en la entrega se penalizará con un 0,1% diario del precio del contrato."
SPECIFICATION = [
    "Alcance. El suministro incluye la entrega de todos los entregables de obra civil descritos en el proyecto.",
    "Calidad. Todos los materiales cumplirán la norma UNE aplicable y se realizarán ensayos de control de calidad.",
]


async def _scored_project(
    db: AsyncSession, worker: Any, user: Any, monkeypatch: pytest.MonkeyPatch
) -> tuple[UUID, Any, Any]:
    """A schedule and a specification that score on their own, plus a contract that raises the advisory."""
    from src.coherence import scoring
    from tests.integration.document_flow.test_contract_schedule_completion_flow import _docx, _xlsx

    # The fixture documents assess fewer categories than a real project: lower the stability threshold so
    # that the other documents still produce a score (the case in which the mirror runs and auto-resolves).
    monkeypatch.setattr(scoring, "MIN_ACTIVE_WEIGHT", 0.1)
    project_id = await _project(db, user.tenant_id)
    await _upload_and_ingest(
        db,
        worker,
        user,
        project_id,
        filename="schedule.xlsx",
        content=_xlsx(LATE_SCHEDULE),
        document_type=DocumentType.SCHEDULE,
    )
    specification, specification_revision = await _upload_and_ingest(
        db,
        worker,
        user,
        project_id,
        filename="spec.docx",
        content=_docx(SPECIFICATION),
        document_type=DocumentType.SPECIFICATION,
    )
    # Approved, as a real project's specification is: a pending one may be withheld from the reading.
    await _trust(db, user, project_id, specification, specification_revision)
    contract, revision = await _upload_and_ingest(
        db,
        worker,
        user,
        project_id,
        filename="contract.docx",
        content=_docx([OBJECT_CLAUSE, PRICE_CLAUSE, COMPLETION_CLAUSE, PENALTY_CLAUSE]),
        document_type=DocumentType.CONTRACT,
    )
    return project_id, contract, revision


async def test_a_pending_new_revision_of_the_contract_does_not_auto_resolve_its_alerts(
    db: AsyncSession, worker: Any, test_user: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A contract raises an alert; a new revision is uploaded and stays PROPOSED; other documents still score.

    The contract is then not evaluated (two revisions and none approved: it has no current revision). That
    must leave its alert exactly as it was: B1 spec 7.4, an incomplete evaluation never auto-resolves, and
    "not evaluated" is never "resolved".
    """
    project_id, contract, _ = await _scored_project(db, worker, test_user, monkeypatch)
    first = await _evaluate(db, test_user, project_id)
    assert first.overall_score is not None
    before = await _alert_row(db, project_id)
    assert before["status"].lower() == "open"

    revision_b = await _reupload_and_ingest(db, worker, test_user, contract, _revised_contract())
    await _propose(db, test_user, project_id, contract, revision_b)
    second = await _evaluate(db, test_user, project_id)

    assert second.overall_score is not None  # the other documents still score
    assert await _alert_row(db, project_id) == before


async def test_a_proposal_on_the_only_revision_of_the_contract_does_not_auto_resolve_its_alerts(
    db: AsyncSession, worker: Any, test_user: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The analysis writes a PROPOSED artifact for the contract that raised an alert (single revision)."""
    project_id, contract, revision = await _scored_project(db, worker, test_user, monkeypatch)
    await _evaluate(db, test_user, project_id)
    before = await _alert_row(db, project_id)

    await _propose(db, test_user, project_id, contract, revision)
    second = await _evaluate(db, test_user, project_id)

    assert second.overall_score is not None
    assert await _alert_row(db, project_id) == before


async def test_a_pending_new_revision_of_any_document_does_not_auto_resolve_its_alerts(
    db: AsyncSession, worker: Any, test_user: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Not only the contract: the schedule that raised the advisory gets a new PROPOSED revision."""
    from tests.integration.document_flow.test_contract_schedule_completion_flow import _xlsx

    project_id, _, _ = await _scored_project(db, worker, test_user, monkeypatch)
    await _evaluate(db, test_user, project_id)
    before = await _alert_row(db, project_id)
    schedule_id = (
        await db.execute(
            text(
                "SELECT id FROM documents WHERE project_id = :p AND document_type::text = 'schedule'"
            ),
            {"p": project_id},
        )
    ).scalar_one()
    schedule = await db.get(DocumentORM, schedule_id)

    revision_b = await _reupload_and_ingest(
        db, worker, test_user, schedule, _xlsx(LATE_SCHEDULE[:-1])
    )
    await _propose(db, test_user, project_id, schedule, revision_b)
    await _evaluate(db, test_user, project_id)

    assert await _alert_row(db, project_id) == before


async def test_a_new_revision_without_any_artifact_does_not_auto_resolve_its_alerts(
    db: AsyncSession, worker: Any, test_user: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Excluded from the evaluation is excluded, with or without a proposal (independent review, P2).

    Two revisions and no artifact at all: the document has no current revision, so it is not read, and
    nothing awaits "approval" in the narrow sense. Its alert must still stay as it was.
    """
    project_id, contract, _ = await _scored_project(db, worker, test_user, monkeypatch)
    await _evaluate(db, test_user, project_id)
    before = await _alert_row(db, project_id)

    await _reupload_and_ingest(db, worker, test_user, contract, _revised_contract())
    second = await _evaluate(db, test_user, project_id)

    assert second.overall_score is not None
    assert await _alert_row(db, project_id) == before


def _wbs_xlsx(version: int) -> bytes:
    from tests.integration.document_flow.test_contract_schedule_completion_flow import _xlsx

    return _xlsx(LATE_SCHEDULE[: len(LATE_SCHEDULE) - version + 1])


async def test_a_reuploaded_wbs_source_never_blocks_the_resolving_of_alerts(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    """A WBS source is never analysed, so its second revision can never be approved: it is not "excluded"."""
    from io import BytesIO

    from fastapi import UploadFile

    from src.documents.adapters.persistence.sqlalchemy_document_repository import (
        SqlAlchemyDocumentRepository,
    )
    from src.documents.application.reupload_document_use_case import ReuploadDocumentUseCase
    from src.documents.application.upload_document_use_case import UploadDocumentUseCase
    from src.temporal.adapters.persistence.project_event_repository import (
        SqlAlchemyProjectEventRepository,
    )
    from tests.integration.document_flow.test_contract_schedule_completion_flow import _ProjectRepo

    project_id = await _project(db, test_user.tenant_id)
    revisions = SqlAlchemyDocumentRevisionRepository(db)
    wbs = await UploadDocumentUseCase(
        document_repository=SqlAlchemyDocumentRepository(db),
        storage_service=worker,
        project_repository=_ProjectRepo(),  # type: ignore[arg-type]
        revision_repository=revisions,
        event_repository=SqlAlchemyProjectEventRepository(db),
    ).execute(
        project_id=project_id,
        file=UploadFile(filename="wbs.xlsx", file=BytesIO(_wbs_xlsx(1))),
        document_type=DocumentType.WBS,
        user_id=test_user.id,
        tenant_id=test_user.tenant_id,
    )
    await ReuploadDocumentUseCase(
        document_repository=SqlAlchemyDocumentRepository(db),
        revision_repository=revisions,
        storage_service=worker,
        event_repository=SqlAlchemyProjectEventRepository(db),
    ).execute(
        tenant_id=test_user.tenant_id,
        document_id=wbs.id,
        file_content=_wbs_xlsx(2),
        user_id=test_user.id,
    )
    await db.commit()
    assert len(await revisions.list_lineage(wbs.id, test_user.tenant_id)) == 2

    assert await _documents_excluded_from_evaluation(db, project_id, test_user.tenant_id) is False


async def test_a_schedule_whose_observation_is_stale_does_not_auto_resolve_its_alerts(
    db: AsyncSession, worker: Any, test_user: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The approved schedule V1 raised the deadline alert; V2 is ingested (not approved) and overwrites the
    observation, so the comparison is not assessable for V1: not evaluated, hence not resolved (round 2, P2)."""
    from tests.integration.document_flow.test_contract_schedule_completion_flow import _xlsx

    project_id, _, _ = await _scored_project(db, worker, test_user, monkeypatch)
    schedule_id = (
        await db.execute(
            text(
                "SELECT id FROM documents WHERE project_id = :p AND document_type::text = 'schedule'"
            ),
            {"p": project_id},
        )
    ).scalar_one()
    schedule = await db.get(DocumentORM, schedule_id)
    [first_revision] = await SqlAlchemyDocumentRevisionRepository(db).list_lineage(
        schedule_id, test_user.tenant_id
    )
    await _trust(db, test_user, project_id, schedule, first_revision)
    await _evaluate(db, test_user, project_id)
    before = await _alert_row(db, project_id)
    assert before["status"].lower() == "open"

    await _reupload_and_ingest(db, worker, test_user, schedule, _xlsx(LATE_SCHEDULE[:-1]))
    second = await _evaluate(db, test_user, project_id)

    assert second.overall_score is not None
    assert await _alert_row(db, project_id) == before


async def test_a_fixed_finding_of_an_approved_revision_still_auto_resolves(
    db: AsyncSession, worker: Any, test_user: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard concerns documents awaiting approval only: an approved revision that fixes the finding resolves it."""
    project_id, contract, _ = await _scored_project(db, worker, test_user, monkeypatch)
    await _evaluate(db, test_user, project_id)
    assert (await _alert_row(db, project_id))["status"].lower() == "open"

    revision_b = await _reupload_and_ingest(db, worker, test_user, contract, _on_time_contract())
    await _trust(db, test_user, project_id, contract, revision_b)
    result = await _evaluate(db, test_user, project_id)

    assert result.overall_score is not None
    assert [a for a in result.alerts if a.rule_id == PROVISIONAL_RULE] == []
    after = await _alert_row(db, project_id)
    assert after["status"].lower() == "resolved" and after["resolved_at"] is not None


def _revised_contract() -> bytes:
    from tests.integration.document_flow.test_contract_schedule_completion_flow import _docx

    return _docx(
        [
            OBJECT_CLAUSE,
            PRICE_CLAUSE,
            "La fecha de finalización de las obras será el 31 de julio de 2027.",
            PENALTY_CLAUSE,
        ]
    )


def _on_time_contract() -> bytes:
    from tests.integration.document_flow.test_contract_schedule_completion_flow import _docx

    return _docx(
        [
            OBJECT_CLAUSE,
            PRICE_CLAUSE,
            "La fecha de finalización de las obras será el 31 de diciembre de 2027.",
            PENALTY_CLAUSE,
        ]
    )


async def test_a_project_whose_only_contract_awaits_approval_gets_an_explicit_state_not_a_404(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    """#1138: the document exists, it is just not canonical input yet. No score, no finding, no write."""
    project_id = await _project(db, test_user.tenant_id)
    contract, revision = await _upload_and_ingest(
        db,
        worker,
        test_user,
        project_id,
        filename="contract.docx",
        content=_other_contract(),
        document_type=DocumentType.CONTRACT,
    )
    await _propose(db, test_user, project_id, contract, revision)

    result = await _evaluate(db, test_user, project_id)

    assert result.overall_score is None and result.alerts == []
    assert result.score_reason == "contract_pending_approval"
    assert result.score_missing_dimensions
    assert (await _alert_count(db, project_id), await _score_rows(db, project_id)) == (0, 0)


async def test_a_project_with_nothing_uploaded_still_answers_404(
    db: AsyncSession, test_user: Any
) -> None:
    from fastapi import HTTPException

    project_id = await _project(db, test_user.tenant_id)

    with pytest.raises(HTTPException) as caught:
        await _evaluate(db, test_user, project_id)

    assert caught.value.status_code == 404


async def _alert_count(db: AsyncSession, project_id: UUID) -> int:
    return int(
        (
            await db.execute(text("SELECT count(*) FROM alerts WHERE project_id = :p"), {"p": project_id})
        ).scalar_one()
    )


async def _score_rows(db: AsyncSession, project_id: UUID) -> int:
    return int(
        (
            await db.execute(
                text("SELECT count(*) FROM coherence_results WHERE project_id = :p"), {"p": project_id}
            )
        ).scalar_one()
    )
