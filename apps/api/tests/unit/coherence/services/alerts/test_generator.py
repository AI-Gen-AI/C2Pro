"""
TS-UD-COH-ALRT-001: Unit tests for AlertGeneratorService and helper methods.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.analysis.application.dtos import AlertCreate
from src.analysis.domain.enums import AlertSeverity, AlertStatus, AlertType
from src.coherence.rules_engine.context_rules import CoherenceRuleResult
from src.coherence.services.alerts.generator import AlertGeneratorService


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
    alert.alert_metadata = {"fingerprint": fingerprint}
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
