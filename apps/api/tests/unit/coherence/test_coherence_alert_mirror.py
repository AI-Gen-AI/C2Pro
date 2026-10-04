"""Line-B contract for mirroring /evaluate findings into durable alerts.

The live path must reconcile through the canonical AlertGeneratorService:
stable identity, tenant/type scope, no destructive batch replacement, and
truthful evidence locators.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.analysis.domain.enums import AlertSeverity
from src.coherence.models import Clause
from src.coherence.router import _mirror_coherence_alerts_to_alerts_table


class _FakeScalarResult:
    def __init__(self, items: list[object]) -> None:
        self._items = items

    def all(self) -> list[object]:
        return list(self._items)


class _FakeSession:
    def __init__(
        self,
        persisted_clause_documents: dict[object, object] | None = None,
    ) -> None:
        self.executed: list[tuple[object, object | None]] = []
        self.persisted_clause_documents = persisted_clause_documents or {}

    async def execute(self, statement: object, params: object | None = None) -> None:
        self.executed.append((statement, params))

    async def scalars(self, statement: object) -> _FakeScalarResult:
        return _FakeScalarResult(
            [
                SimpleNamespace(id=clause_id, document_id=document_id)
                for clause_id, document_id in self.persisted_clause_documents.items()
            ]
        )


@pytest.mark.asyncio
async def test_mirror_reconciles_via_canonical_service_with_evidence_locator() -> None:
    project_id = uuid4()
    tenant_id = uuid4()
    clause_id = uuid4()
    document_id = uuid4()
    alert = SimpleNamespace(
        severity="critical",
        category="schedule",
        rule_id="DET-TIM-GAP",
        message="Milestone gap exceeds tolerance",
        evidence=SimpleNamespace(
            source_clause_id=str(clause_id),
            claim="Schedule gap detected",
            quote="Milestone B starts thirty days later",
        ),
    )
    clauses = [
        Clause(
            id=str(clause_id),
            text="Milestone B starts thirty days later",
            data={"document_id": str(document_id), "source": "persisted_clause"},
        )
    ]
    session = _FakeSession(persisted_clause_documents={clause_id: document_id})
    service = MagicMock()
    service.process_violations = AsyncMock(return_value=[])

    with (
        patch("src.coherence.router.SqlAlchemyAlertRepository") as repo_cls,
        patch("src.coherence.router.AlertGeneratorService", return_value=service),
    ):
        await _mirror_coherence_alerts_to_alerts_table(
            db=session,  # type: ignore[arg-type]
            project_id=project_id,
            tenant_id=tenant_id,
            alerts=[alert],
            clauses=clauses,
        )

    repo_cls.assert_called_once_with(session)
    assert len(session.executed) == 1
    statement, params = session.executed[0]
    assert "pg_advisory_xact_lock" in str(statement)
    assert params == {"mirror_key": f"coherence-alerts:{tenant_id}:{project_id}"}

    kwargs = service.process_violations.await_args.kwargs
    assert kwargs["project_id"] == project_id
    assert kwargs["tenant_id"] == tenant_id
    assert kwargs["auto_resolve"] is True
    assert kwargs["commit"] is False
    assert len(kwargs["violations"]) == 1
    payload = kwargs["violations"][0]
    assert payload.severity == AlertSeverity.CRITICAL
    assert payload.category == "TIME"
    assert payload.rule_id == "DET-TIM-GAP"
    assert payload.source_clause_id == clause_id
    assert payload.affected_entities == {"documents": [str(document_id)]}
    assert payload.alert_metadata["detection_evidence"] == {
        "source_clause_id": str(clause_id),
        "source_document_id": str(document_id),
        "claim": "Schedule gap detected",
        "quote": "Milestone B starts thirty days later",
    }


@pytest.mark.asyncio
async def test_verified_clause_uses_database_document_not_request_metadata() -> None:
    project_id = uuid4()
    tenant_id = uuid4()
    clause_id = uuid4()
    canonical_document_id = uuid4()
    forged_document_id = uuid4()
    alert = SimpleNamespace(
        severity="high",
        category="legal",
        rule_id="DET-LEG-PROVENANCE",
        message="Verified clause provenance",
        evidence=SimpleNamespace(
            source_clause_id=str(clause_id),
            claim="Persisted clause",
            quote="Canonical source",
        ),
    )
    clauses = [
        Clause(
            id=str(clause_id),
            text="Canonical source",
            data={
                "document_id": str(forged_document_id),
                "source": "persisted_clause",
            },
        )
    ]
    session = _FakeSession(
        persisted_clause_documents={clause_id: canonical_document_id}
    )
    service = MagicMock()
    service.process_violations = AsyncMock(return_value=[])

    with (
        patch("src.coherence.router.SqlAlchemyAlertRepository"),
        patch("src.coherence.router.AlertGeneratorService", return_value=service),
    ):
        await _mirror_coherence_alerts_to_alerts_table(
            db=session,  # type: ignore[arg-type]
            project_id=project_id,
            tenant_id=tenant_id,
            alerts=[alert],
            clauses=clauses,
        )

    payload = service.process_violations.await_args.kwargs["violations"][0]
    assert payload.source_clause_id == clause_id
    assert payload.affected_entities == {
        "documents": [str(canonical_document_id)]
    }
    assert payload.alert_metadata["detection_evidence"]["source_document_id"] == str(
        canonical_document_id
    )


@pytest.mark.asyncio
async def test_uuid_looking_external_locator_is_not_used_as_clause_foreign_key() -> None:
    project_id = uuid4()
    tenant_id = uuid4()
    external_locator = uuid4()
    document_id = uuid4()
    alert = SimpleNamespace(
        severity="high",
        category="legal",
        rule_id="DET-LEG-EXTERNAL",
        message="External clause locator",
        evidence=SimpleNamespace(
            source_clause_id=str(external_locator),
            claim="Caller-provided locator",
            quote="External text",
        ),
    )
    clauses = [
        Clause(
            id=str(external_locator),
            text="External text",
            data={
                "document_id": str(document_id),
                "source": "persisted_clause",
            },
        )
    ]
    session = _FakeSession()
    service = MagicMock()
    service.process_violations = AsyncMock(return_value=[])

    with (
        patch("src.coherence.router.SqlAlchemyAlertRepository"),
        patch("src.coherence.router.AlertGeneratorService", return_value=service),
    ):
        await _mirror_coherence_alerts_to_alerts_table(
            db=session,  # type: ignore[arg-type]
            project_id=project_id,
            tenant_id=tenant_id,
            alerts=[alert],
            clauses=clauses,
        )

    payload = service.process_violations.await_args.kwargs["violations"][0]
    assert payload.source_clause_id is None
    assert payload.alert_metadata["detection_evidence"]["source_clause_id"] == str(
        external_locator
    )
    assert payload.alert_metadata["detection_evidence"]["source_document_id"] == str(
        document_id
    )


@pytest.mark.asyncio
async def test_mirror_keeps_unresolvable_locator_as_text_but_not_fake_uuid_fk() -> None:
    project_id = uuid4()
    tenant_id = uuid4()
    alert = SimpleNamespace(
        severity="bogus",
        category="general",
        rule_id="AUDIT_INCOMPLETE",
        message="",
        evidence=SimpleNamespace(
            source_clause_id="parsed_deadbeef",
            claim="Missing dimensions",
            quote="",
        ),
    )
    clauses = [
        Clause(
            id="parsed_deadbeef",
            text="Fallback parsed text",
            data={"document_id": "doc-fallback"},
        )
    ]
    session = _FakeSession()
    service = MagicMock()
    service.process_violations = AsyncMock(return_value=[])

    with (
        patch("src.coherence.router.SqlAlchemyAlertRepository"),
        patch("src.coherence.router.AlertGeneratorService", return_value=service),
    ):
        await _mirror_coherence_alerts_to_alerts_table(
            db=session,  # type: ignore[arg-type]
            project_id=project_id,
            tenant_id=tenant_id,
            alerts=[alert],
            clauses=clauses,
        )

    payload = service.process_violations.await_args.kwargs["violations"][0]
    assert payload.severity == AlertSeverity.MEDIUM
    assert payload.category == "SCOPE"
    assert payload.source_clause_id is None
    assert payload.alert_metadata["detection_evidence"]["source_clause_id"] == "parsed_deadbeef"
    assert payload.alert_metadata["detection_evidence"]["source_document_id"] == "doc-fallback"


@pytest.mark.asyncio
async def test_empty_evaluation_reconciles_empty_set_instead_of_deleting_history() -> None:
    session = _FakeSession()
    service = MagicMock()
    service.process_violations = AsyncMock(return_value=[])
    project_id = uuid4()
    tenant_id = uuid4()

    with (
        patch("src.coherence.router.SqlAlchemyAlertRepository"),
        patch("src.coherence.router.AlertGeneratorService", return_value=service),
    ):
        await _mirror_coherence_alerts_to_alerts_table(
            db=session,  # type: ignore[arg-type]
            project_id=project_id,
            tenant_id=tenant_id,
            alerts=[],
            clauses=[],
        )

    kwargs = service.process_violations.await_args.kwargs
    assert kwargs["violations"] == []
    assert kwargs["auto_resolve"] is True
    assert kwargs["commit"] is False


@pytest.mark.asyncio
async def test_persisted_clause_document_provenance_comes_from_database() -> None:
    project_id = uuid4()
    tenant_id = uuid4()
    clause_id = uuid4()
    canonical_document_id = uuid4()
    forged_document_id = uuid4()
    alert = SimpleNamespace(
        severity="high",
        category="schedule",
        rule_id="DET-TIM-GAP",
        message="Schedule gap",
        evidence=SimpleNamespace(
            source_clause_id=str(clause_id),
            claim="Persisted clause finding",
            quote="Canonical clause text",
        ),
    )
    clauses = [
        Clause(
            id=str(clause_id),
            text="Canonical clause text",
            data={
                "document_id": str(forged_document_id),
                "source": "persisted_clause",
            },
        )
    ]
    session = _FakeSession()
    service = MagicMock()
    service.process_violations = AsyncMock(return_value=[])

    with (
        patch("src.coherence.router.SqlAlchemyAlertRepository"),
        patch("src.coherence.router.AlertGeneratorService", return_value=service),
        patch(
            "src.coherence.router._verified_persisted_clause_ids",
            new=AsyncMock(
                return_value={clause_id: canonical_document_id}
            ),
        ),
    ):
        await _mirror_coherence_alerts_to_alerts_table(
            db=session,  # type: ignore[arg-type]
            project_id=project_id,
            tenant_id=tenant_id,
            alerts=[alert],
            clauses=clauses,
        )

    payload = service.process_violations.await_args.kwargs["violations"][0]
    assert payload.source_clause_id == clause_id
    assert payload.affected_entities == {
        "documents": [str(canonical_document_id)]
    }
    assert payload.alert_metadata["detection_evidence"]["source_document_id"] == str(
        canonical_document_id
    )
