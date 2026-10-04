"""
TS-UD-COH-ALRT-001: Unit tests for AlertGeneratorService and helper methods.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.analysis.application.dtos import AlertCreate
from src.analysis.domain.enums import AlertSeverity, AlertStatus, AlertType
from src.coherence.rules_engine.context_rules import CoherenceRuleResult
from src.coherence.services.alerts.generator import (
    FINGERPRINT_VERSION,
    AlertGeneratorService,
)


def _make_alert_create(
    rule_id: str = "DET-SCP-DELIVERABLES",
    severity: AlertSeverity = AlertSeverity.MEDIUM,
    title: str = "Test alert",
    description: str = "Test description",
    category: str = "SCOPE",
    source_clause_id: uuid4 | None = None,
    affected_entities: dict | None = None,
) -> AlertCreate:
    return AlertCreate(
        project_id=uuid4(),
        alert_type=AlertType.COHERENCE,
        title=title,
        description=description,
        severity=severity,
        rule_id=rule_id,
        category=category,
        source_clause_id=source_clause_id,
        affected_entities=affected_entities or {},
    )


def _make_mock_alert(
    alert_id: uuid4 | None = None,
    status: AlertStatus = AlertStatus.OPEN,
    fingerprint: str = "abc123",
    severity: AlertSeverity = AlertSeverity.MEDIUM,
) -> MagicMock:
    alert = MagicMock()
    alert.id = alert_id or uuid4()
    alert.status = status
    alert.severity = severity
    alert.alert_metadata = {
        "fingerprint": fingerprint,
        "fingerprint_version": FINGERPRINT_VERSION,
    }
    alert.project_id = uuid4()
    alert.category = None
    alert.rule_id = None
    alert.title = ""
    alert.description = ""
    alert.recommendation = None
    alert.source_clause_id = None
    alert.related_clause_ids = None
    alert.affected_entities = {}
    alert.impact_level = None
    alert.resolved_at = None
    alert.resolved_by = None
    alert.resolution_notes = None
    return alert


def _make_mock_page(items: list, has_more: bool = False) -> MagicMock:
    page = MagicMock()
    page.items = items
    page.has_more = has_more
    page.next_cursor = "cursor_next" if has_more else None
    return page


class TestFingerprint:
    def test_fingerprint_deterministic(self) -> None:
        alert1 = _make_alert_create(rule_id="R1", affected_entities={"wbs": ["id1", "id2"]})
        alert2 = _make_alert_create(rule_id="R1", affected_entities={"wbs": ["id2", "id1"]})
        svc = AlertGeneratorService(repository=MagicMock())
        fp1 = svc._fingerprint(alert1)
        fp2 = svc._fingerprint(alert2)
        assert fp1 == fp2

    def test_fingerprint_different_rules(self) -> None:
        alert1 = _make_alert_create(rule_id="R1")
        alert2 = _make_alert_create(rule_id="R2")
        svc = AlertGeneratorService(repository=MagicMock())
        assert svc._fingerprint(alert1) != svc._fingerprint(alert2)

    def test_fingerprint_with_source_clause(self) -> None:
        clause_id = uuid4()
        alert = _make_alert_create(rule_id="R1", source_clause_id=clause_id)
        svc = AlertGeneratorService(repository=MagicMock())
        fp = svc._fingerprint(alert)
        assert len(fp) == 64  # SHA-256 hex


    def test_legacy_text_locator_matches_new_detection_evidence_identity(self) -> None:
        svc = AlertGeneratorService(repository=MagicMock())
        existing = _make_mock_alert(fingerprint="")
        existing.rule_id = "AUDIT_INCOMPLETE"
        existing.category = "SCOPE"
        existing.alert_metadata = {
            "evidence": {
                "source_clause_id": "parsed_deadbeef",
                "claim": "Missing dimensions",
                "quote": "",
            }
        }

        incoming = _make_alert_create(
            rule_id="AUDIT_INCOMPLETE",
            category="SCOPE",
            affected_entities={"documents": ["doc-fallback"]},
        )
        incoming.alert_metadata = {
            "detection_evidence": {
                "source_clause_id": "parsed_deadbeef",
                "source_document_id": "doc-fallback",
                "claim": "Missing dimensions",
                "quote": "",
            }
        }

        assert svc._fingerprint_existing(existing) == svc._fingerprint(incoming)


    def test_positional_rag_locator_does_not_own_finding_identity(self) -> None:
        svc = AlertGeneratorService(repository=MagicMock())
        first = _make_alert_create(
            rule_id="DET-LEG-RAG",
            category="LEGAL",
            affected_entities={"documents": ["doc-123"]},
        )
        first.alert_metadata = {
            "detection_evidence": {
                "source_clause_id": "chunk_0_deadbeef",
                "source_document_id": "doc-123",
                "claim": "Notice period mismatch",
                "quote": "Notice shall be thirty days",
            }
        }
        second = first.model_copy(deep=True)
        second.alert_metadata = {
            "detection_evidence": {
                "source_clause_id": "chunk_9_deadbeef",
                "source_document_id": "doc-123",
                "claim": "Notice period mismatch",
                "quote": "Notice shall be thirty days",
            }
        }

        assert svc._fingerprint(first) == svc._fingerprint(second)

    def test_existing_positional_rag_locator_matches_renumbered_incoming_finding(self) -> None:
        svc = AlertGeneratorService(repository=MagicMock())
        existing = _make_mock_alert(fingerprint="")
        existing.rule_id = "DET-LEG-RAG"
        existing.alert_metadata = {
            "detection_evidence": {
                "source_clause_id": "chunk_1_deadbeef",
                "source_document_id": "doc-123",
                "claim": "Notice period mismatch",
                "quote": "Notice shall be thirty days",
            }
        }
        incoming = _make_alert_create(
            rule_id="DET-LEG-RAG",
            category="LEGAL",
            affected_entities={"documents": ["doc-123"]},
        )
        incoming.alert_metadata = {
            "detection_evidence": {
                "source_clause_id": "chunk_7_deadbeef",
                "source_document_id": "doc-123",
                "claim": "Notice period mismatch",
                "quote": "Notice shall be thirty days",
            }
        }

        assert svc._fingerprint_existing(existing) == svc._fingerprint(incoming)


    def test_stored_legacy_fingerprint_is_recomputed_with_current_identity_scheme(self) -> None:
        clause_id = uuid4()
        svc = AlertGeneratorService(repository=MagicMock())
        existing = _make_mock_alert(fingerprint="legacy-v1-digest")
        existing.alert_metadata = {
            "fingerprint": "legacy-v1-digest",
            "fingerprint_version": 1,
        }
        existing.rule_id = "DET-SCP-DELIVERABLES"
        existing.category = "SCOPE"
        existing.source_clause_id = clause_id
        existing.affected_entities = {"documents": ["doc-1"]}

        incoming = _make_alert_create(
            rule_id="DET-SCP-DELIVERABLES",
            category="SCOPE",
            source_clause_id=clause_id,
            affected_entities={"documents": ["doc-1"]},
        )

        current = svc._fingerprint(incoming)
        assert current != "legacy-v1-digest"
        assert svc._fingerprint_existing(existing) == current


class TestFlattenEntities:
    def test_flattens_dict_values(self) -> None:
        svc = AlertGeneratorService(repository=MagicMock())
        result = svc._flatten_entities({"wbs": ["a", "b"], "bom": ["c"]})
        assert sorted(result) == ["a", "b", "c"]

    def test_empty_payload(self) -> None:
        svc = AlertGeneratorService(repository=MagicMock())
        assert svc._flatten_entities({}) == []

    def test_none_payload(self) -> None:
        svc = AlertGeneratorService(repository=MagicMock())
        assert svc._flatten_entities(None) == []  # type: ignore[arg-type]


class TestMergeNotes:
    def test_appends_new_note(self) -> None:
        svc = AlertGeneratorService(repository=MagicMock())
        result = svc._merge_notes("Old note", "New note")
        assert result == "Old note | New note"

    def test_existing_is_none(self) -> None:
        svc = AlertGeneratorService(repository=MagicMock())
        assert svc._merge_notes(None, "Only note") == "Only note"

    def test_duplicate_not_appended(self) -> None:
        svc = AlertGeneratorService(repository=MagicMock())
        result = svc._merge_notes("Existing note", "Existing note")
        assert result == "Existing note"


class TestRequiresHumanReview:
    def test_critical_requires_review(self) -> None:
        svc = AlertGeneratorService(repository=MagicMock())
        alert = _make_alert_create(severity=AlertSeverity.CRITICAL)
        assert svc._requires_human_review(alert) is True

    def test_high_requires_review(self) -> None:
        svc = AlertGeneratorService(repository=MagicMock())
        alert = _make_alert_create(severity=AlertSeverity.HIGH)
        assert svc._requires_human_review(alert) is True

    def test_medium_does_not_require(self) -> None:
        svc = AlertGeneratorService(repository=MagicMock())
        alert = _make_alert_create(severity=AlertSeverity.MEDIUM, rule_id="DET-QUA-STANDARD")
        assert svc._requires_human_review(alert) is False

    def test_penal_rule_requires_review(self) -> None:
        svc = AlertGeneratorService(repository=MagicMock())
        alert = _make_alert_create(severity=AlertSeverity.MEDIUM, rule_id="DET-LEG-PENALTY")
        assert svc._requires_human_review(alert) is True


class TestBuildMetadata:
    def test_includes_fingerprint_and_review_flag(self) -> None:
        svc = AlertGeneratorService(repository=MagicMock())
        alert = _make_alert_create(severity=AlertSeverity.CRITICAL)
        metadata = svc._build_metadata(alert, "fp123")
        assert metadata["fingerprint"] == "fp123"
        assert metadata["requires_human_review"] is True

    def test_preserves_existing_metadata(self) -> None:
        svc = AlertGeneratorService(repository=MagicMock())
        alert = _make_alert_create(severity=AlertSeverity.LOW)
        alert.alert_metadata = {"existing_key": "value"}
        metadata = svc._build_metadata(alert, "fp")
        assert metadata["existing_key"] == "value"


class TestProcessViolations:
    @pytest.mark.asyncio
    async def test_creates_new_alert(self) -> None:
        repo = MagicMock()
        repo.list_for_project = AsyncMock(return_value=_make_mock_page([]))
        repo.create = AsyncMock(return_value=_make_mock_alert())
        repo.update = AsyncMock()
        repo.commit = AsyncMock()

        svc = AlertGeneratorService(repository=repo)
        alert = _make_alert_create(rule_id="NEW_RULE")
        result = await svc.process_violations(project_id=uuid4(), violations=[alert])

        assert len(result) == 1
        repo.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_updates_existing_open_alert(self) -> None:
        existing = _make_mock_alert(status=AlertStatus.OPEN, fingerprint="fp-match")
        repo = MagicMock()
        repo.list_for_project = AsyncMock(return_value=_make_mock_page([existing]))
        repo.update = AsyncMock()
        repo.commit = AsyncMock()

        svc = AlertGeneratorService(repository=repo)
        alert = _make_alert_create(rule_id="SAME_RULE", affected_entities={"wbs": ["w1"]})
        # Force the same fingerprint
        with patch("src.coherence.services.alerts.generator.AlertGeneratorService._fingerprint", return_value="fp-match"):
            result = await svc.process_violations(project_id=uuid4(), violations=[alert])

        assert len(result) == 1
        repo.update.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reopens_resolved_alert(self) -> None:
        existing = _make_mock_alert(status=AlertStatus.RESOLVED, fingerprint="fp-reopen")
        repo = MagicMock()
        repo.list_for_project = AsyncMock(return_value=_make_mock_page([existing]))
        repo.update = AsyncMock()
        repo.commit = AsyncMock()

        svc = AlertGeneratorService(repository=repo)
        alert = _make_alert_create(rule_id="REOPEN_RULE")

        with patch("src.coherence.services.alerts.generator.AlertGeneratorService._fingerprint", return_value="fp-reopen"):
            result = await svc.process_violations(project_id=uuid4(), violations=[alert])

        assert result[0].status == AlertStatus.OPEN
        assert result[0].resolved_at is None

    @pytest.mark.asyncio
    async def test_auto_resolves_missing_violations(self) -> None:
        existing = _make_mock_alert(status=AlertStatus.OPEN, fingerprint="old-fp")
        repo = MagicMock()
        repo.list_for_project = AsyncMock(return_value=_make_mock_page([existing]))
        repo.create = AsyncMock(return_value=_make_mock_alert())
        repo.update = AsyncMock()
        repo.commit = AsyncMock()

        svc = AlertGeneratorService(repository=repo)
        alert = _make_alert_create(rule_id="DIFFERENT")

        with patch("src.coherence.services.alerts.generator.AlertGeneratorService._fingerprint", side_effect=lambda v: "new-fp"):
            await svc.process_violations(project_id=uuid4(), violations=[alert], auto_resolve=True)
        # existing alert should be resolved
        resolved_calls = [
            call for call in repo.update.call_args_list
            if call[0][0] is existing
        ]
        assert len(resolved_calls) >= 1

    @pytest.mark.asyncio
    async def test_acknowledged_finding_survives_temporary_detector_miss(self) -> None:
        existing = _make_mock_alert(
            status=AlertStatus.ACKNOWLEDGED,
            fingerprint="accepted-fp",
        )
        reviewer = uuid4()
        existing.reviewed_by = reviewer
        existing.review_comment = "Accepted contractual variance"
        repo = MagicMock()
        repo.list_for_project = AsyncMock(return_value=_make_mock_page([existing]))
        repo.create = AsyncMock()
        repo.update = AsyncMock()
        repo.commit = AsyncMock()

        svc = AlertGeneratorService(repository=repo)
        await svc.process_violations(
            project_id=uuid4(),
            violations=[],
            auto_resolve=True,
        )

        assert existing.status == AlertStatus.ACKNOWLEDGED
        assert existing.reviewed_by == reviewer
        assert existing.review_comment == "Accepted contractual variance"
        repo.update.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_auto_resolve_when_disabled(self) -> None:
        existing = _make_mock_alert(status=AlertStatus.OPEN, fingerprint="old-fp")
        repo = MagicMock()
        repo.list_for_project = AsyncMock(return_value=_make_mock_page([existing]))
        repo.create = AsyncMock(return_value=_make_mock_alert())
        repo.update = AsyncMock()
        repo.commit = AsyncMock()

        svc = AlertGeneratorService(repository=repo)
        alert = _make_alert_create(rule_id="DIFFERENT")

        with patch("src.coherence.services.alerts.generator.AlertGeneratorService._fingerprint", return_value="new-fp"):
            await svc.process_violations(project_id=uuid4(), violations=[alert], auto_resolve=False)

        # existing alert should NOT have been touched for resolution
        for call in repo.update.call_args_list:
            assert call[0][0] is not existing or getattr(call[0][0], 'status', None) != AlertStatus.RESOLVED


from unittest.mock import patch


class _StatefulAlertRepo:
    """In-memory alert repository that mimics real create/list/update semantics.

    Unlike the per-test MagicMocks above, this repo *persists* created alerts so
    that a subsequent ``process_violations`` run sees the alerts from the prior
    run — the exact condition under which re-analysis could double-count.
    """

    def __init__(self) -> None:
        self._alerts: list[SimpleNamespace] = []
        self.create_calls = 0
        self.update_calls = 0

    async def list_for_project(
        self, project_id, tenant_id=None, alert_type=None, cursor=None, limit=200
    ):  # noqa: ANN001, ARG002
        return _make_mock_page(list(self._alerts), has_more=False)

    async def create(self, payload):  # noqa: ANN001
        self.create_calls += 1
        record = SimpleNamespace(
            id=uuid4(),
            status=AlertStatus.OPEN,
            alert_metadata=dict(payload.alert_metadata or {}),
            severity=payload.severity,
            category=payload.category,
            rule_id=payload.rule_id,
            title=payload.title,
            description=payload.description,
            recommendation=getattr(payload, "recommendation", None),
            source_clause_id=payload.source_clause_id,
            related_clause_ids=getattr(payload, "related_clause_ids", None),
            affected_entities=payload.affected_entities,
            impact_level=getattr(payload, "impact_level", None),
            resolved_at=None,
            resolved_by=None,
            resolution_notes=None,
        )
        self._alerts.append(record)
        return record

    async def update(self, alert):  # noqa: ANN001
        self.update_calls += 1

    async def commit(self):
        pass

    @property
    def open_count(self) -> int:
        return sum(1 for a in self._alerts if a.status == AlertStatus.OPEN)


class TestReanalysisSupersedesRatherThanAccumulates:
    """TASK-HOTFIX-F2: a 2nd analysis must not double the alert count."""

    @pytest.mark.asyncio
    async def test_second_run_with_same_violations_does_not_double_count(self) -> None:
        repo = _StatefulAlertRepo()
        svc = AlertGeneratorService(repository=repo)
        project_id = uuid4()
        violations = [
            _make_alert_create(rule_id="DET-SCP-DELIVERABLES", category="SCOPE"),
            _make_alert_create(rule_id="DET-BUD-INTERNAL", category="BUDGET"),
            _make_alert_create(rule_id="DET-LEG-PENALTY", category="LEGAL"),
        ]

        first = await svc.process_violations(project_id=project_id, violations=violations)
        assert len(first) == 3
        assert repo.create_calls == 3
        assert repo.open_count == 3

        # Re-run analysis with the *same* violations — must supersede, not stack.
        second = await svc.process_violations(project_id=project_id, violations=violations)
        assert len(second) == 3
        # No new alerts were created on the second run …
        assert repo.create_calls == 3
        # … existing ones were updated in place instead.
        assert repo.update_calls == 3
        # Total persisted alerts stays at 3 (not 6).
        assert len(repo._alerts) == 3
        assert repo.open_count == 3

    @pytest.mark.asyncio
    async def test_dropped_violation_is_auto_resolved_on_reanalysis(self) -> None:
        repo = _StatefulAlertRepo()
        svc = AlertGeneratorService(repository=repo)
        project_id = uuid4()
        run_one = [
            _make_alert_create(rule_id="DET-SCP-DELIVERABLES", category="SCOPE"),
            _make_alert_create(rule_id="DET-BUD-INTERNAL", category="BUDGET"),
        ]
        await svc.process_violations(project_id=project_id, violations=run_one)
        assert repo.open_count == 2

        # Second run only re-detects one violation; the other must be auto-resolved,
        # not left dangling as a stacked open alert.
        run_two = [_make_alert_create(rule_id="DET-SCP-DELIVERABLES", category="SCOPE")]
        await svc.process_violations(project_id=project_id, violations=run_two)

        assert len(repo._alerts) == 2  # still no duplicates created
        assert repo.create_calls == 2
        assert repo.open_count == 1  # the dropped violation was auto-resolved


class TestProcessRuleResults:
    @pytest.mark.asyncio
    async def test_converts_rule_results_to_alerts(self) -> None:
        repo = MagicMock()
        repo.list_for_project = AsyncMock(return_value=_make_mock_page([]))
        repo.create = AsyncMock(return_value=_make_mock_alert())
        repo.update = AsyncMock()
        repo.commit = AsyncMock()

        svc = AlertGeneratorService(repository=repo)
        p_id = uuid4()
        rule_result = CoherenceRuleResult(
            rule_id="DET-SCP-DELIVERABLES",
            is_violated=True,
            evidence={"deliverable_name": "Foundation"},
        )
        result = await svc.process_rule_results(project_id=p_id, rule_results=[rule_result])
        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_non_violated_rules_skipped(self) -> None:
        repo = MagicMock()
        repo.list_for_project = AsyncMock(return_value=_make_mock_page([]))
        repo.create = AsyncMock()
        repo.update = AsyncMock()
        repo.commit = AsyncMock()

        svc = AlertGeneratorService(repository=repo)
        rule_result = CoherenceRuleResult(rule_id="ANY_RULE", is_violated=False)
        result = await svc.process_rule_results(project_id=uuid4(), rule_results=[rule_result])
        assert result == []
        repo.create.assert_not_awaited()


class TestLineBStableFindingIdentity:
    @pytest.mark.asyncio
    async def test_reanalysis_scopes_existing_lookup_to_tenant_and_coherence_type(self) -> None:
        repo = MagicMock()
        repo.list_for_project = AsyncMock(return_value=_make_mock_page([]))
        repo.create = AsyncMock(return_value=_make_mock_alert())
        repo.update = AsyncMock()
        repo.commit = AsyncMock()
        svc = AlertGeneratorService(repository=repo)
        project_id = uuid4()
        tenant_id = uuid4()

        await svc.process_violations(
            project_id=project_id,
            tenant_id=tenant_id,
            violations=[_make_alert_create(rule_id="DET-SCP-DELIVERABLES")],
        )

        repo.list_for_project.assert_awaited_once_with(
            project_id=project_id,
            tenant_id=tenant_id,
            alert_type=AlertType.COHERENCE,
            cursor=None,
            limit=200,
        )

    @pytest.mark.asyncio
    async def test_same_acknowledged_finding_preserves_human_disposition_and_metadata(self) -> None:
        reviewer = uuid4()
        existing = _make_mock_alert(status=AlertStatus.ACKNOWLEDGED, fingerprint="stable-fp")
        existing.reviewed_by = reviewer
        existing.review_comment = "Accepted contractual variance"
        existing.alert_metadata = {
            "fingerprint": "stable-fp",
            "fingerprint_version": FINGERPRINT_VERSION,
            "history": [{"action": "reviewed", "decision": "approve"}],
            "evidence": [{"type": "note", "content": "Reviewer evidence"}],
            "detection_evidence": {"claim": "old claim", "quote": "old quote"},
        }
        repo = MagicMock()
        repo.list_for_project = AsyncMock(return_value=_make_mock_page([existing]))
        repo.update = AsyncMock()
        repo.commit = AsyncMock()
        svc = AlertGeneratorService(repository=repo)
        incoming = _make_alert_create(rule_id="DET-SCP-DELIVERABLES")
        incoming.alert_metadata = {
            "detection_evidence": {"claim": "fresh claim", "quote": "fresh quote"}
        }

        with patch(
            "src.coherence.services.alerts.generator.AlertGeneratorService._fingerprint",
            return_value="stable-fp",
        ):
            result = await svc.process_violations(
                project_id=uuid4(), tenant_id=uuid4(), violations=[incoming]
            )

        same = result[0]
        assert same is existing
        assert same.status == AlertStatus.ACKNOWLEDGED
        assert same.reviewed_by == reviewer
        assert same.review_comment == "Accepted contractual variance"
        assert same.alert_metadata["history"] == [
            {"action": "reviewed", "decision": "approve"}
        ]
        assert same.alert_metadata["evidence"] == [
            {"type": "note", "content": "Reviewer evidence"}
        ]
        assert same.alert_metadata["detection_evidence"]["claim"] == "fresh claim"

    @pytest.mark.asyncio
    async def test_same_dismissed_false_positive_does_not_reopen(self) -> None:
        existing = _make_mock_alert(status=AlertStatus.DISMISSED, fingerprint="false-positive-fp")
        existing.review_comment = "False positive confirmed"
        existing.resolution_notes = "False positive confirmed"
        repo = MagicMock()
        repo.list_for_project = AsyncMock(return_value=_make_mock_page([existing]))
        repo.update = AsyncMock()
        repo.commit = AsyncMock()
        svc = AlertGeneratorService(repository=repo)
        incoming = _make_alert_create(rule_id="DET-SCP-DELIVERABLES")

        with patch(
            "src.coherence.services.alerts.generator.AlertGeneratorService._fingerprint",
            return_value="false-positive-fp",
        ):
            result = await svc.process_violations(
                project_id=uuid4(), tenant_id=uuid4(), violations=[incoming]
            )

        assert result[0] is existing
        assert existing.status == AlertStatus.DISMISSED
        assert existing.review_comment == "False positive confirmed"
        assert existing.resolution_notes == "False positive confirmed"

    @pytest.mark.asyncio
    async def test_duplicate_findings_in_one_evaluation_create_one_alert(self) -> None:
        repo = MagicMock()
        repo.list_for_project = AsyncMock(return_value=_make_mock_page([]))
        repo.create = AsyncMock(side_effect=lambda payload: _make_mock_alert())
        repo.update = AsyncMock()
        repo.commit = AsyncMock()
        svc = AlertGeneratorService(repository=repo)
        same = _make_alert_create(rule_id="DET-SCP-DELIVERABLES")

        with patch(
            "src.coherence.services.alerts.generator.AlertGeneratorService._fingerprint",
            return_value="same-fp",
        ):
            result = await svc.process_violations(
                project_id=uuid4(), tenant_id=uuid4(), violations=[same, same]
            )

        assert len(result) == 1
        assert repo.create.await_count == 1
