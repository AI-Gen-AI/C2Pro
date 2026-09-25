"""Tests for PersistAnalysisUseCase.

TASK-IMPL-010.7: Persistence orchestration — saves analysis, alerts, WBS.
Uses mocked ORM models to avoid SQLAlchemy mapper initialization issues.
"""

from __future__ import annotations

import sys
from collections.abc import Generator
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from src.analysis.domain.enums import AnalysisStatus, AnalysisType

# Pre-register stub ORM modules to avoid SQLAlchemy mapper chain.
# The use case lazy-imports these inside execute().
_stub_analysis_models = ModuleType("src.analysis.adapters.persistence.models")


class _StubAnalysis:
    """Minimal Analysis stand-in for unit tests."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        if not hasattr(self, "id"):
            self.id = uuid4()


class _StubAlert:
    """Minimal Alert stand-in for unit tests."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


_stub_analysis_models.Analysis = _StubAnalysis  # type: ignore[attr-defined]
_stub_analysis_models.Alert = _StubAlert  # type: ignore[attr-defined]

_stub_wbs_models = ModuleType("src.procurement.adapters.persistence.models")


class _StubWBSItemORM:
    project_id = "project_id"


_stub_wbs_models.WBSItemORM = _StubWBSItemORM  # type: ignore[attr-defined]

# Stub AlertGenerator
_stub_alert_gen_mod = ModuleType("src.coherence.alert_generator")


class _StubAlertGenerator:
    def __init__(self, **kwargs):
        pass

    def generate_risk_alerts(self, risks):
        return [
            MagicMock(
                project_id=uuid4(),
                analysis_id=uuid4(),
                alert_type="risk",
                severity="high",
                title=r.get("title", ""),
                description="",
                category=r.get("category", ""),
                impact_level=r.get("impact", ""),
                alert_metadata={},
                rule_id=None,
                source_clause_id=None,
                related_clause_ids=[],
                affected_entities=[],
                recommendation=None,
            )
            for r in risks
        ]


_stub_alert_gen_mod.AlertGenerator = _StubAlertGenerator  # type: ignore[attr-defined]

_STUB_MODULES = {
    "src.analysis.adapters.persistence.models": _stub_analysis_models,
    "src.procurement.adapters.persistence.models": _stub_wbs_models,
    "src.coherence.alert_generator": _stub_alert_gen_mod,
}


@pytest.fixture(autouse=True)
def _isolate_sys_modules() -> Generator[None, None, None]:
    """Inject stub modules only for the duration of each test.

    The use case lazy-imports these inside execute().  Using a fixture
    avoids polluting sys.modules for the rest of the test session.
    """
    saved: dict[str, object] = {}
    for name, stub in _STUB_MODULES.items():
        saved[name] = sys.modules.get(name)
        sys.modules[name] = stub
    yield
    for name, original in saved.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original

from src.analysis.application.persist_analysis_use_case import (
    PersistAnalysisCommand,
    PersistAnalysisResult,
    PersistAnalysisUseCase,
)


def _make_command(**overrides) -> PersistAnalysisCommand:
    defaults = {
        "project_id": uuid4(),
        "tenant_id": uuid4(),
        "extracted_risks": [],
        "extracted_wbs": [],
        "coherence_score": 75,
        "coherence_breakdown": {"LEGAL": 80},
    }
    defaults.update(overrides)
    return PersistAnalysisCommand(**defaults)


class TestPersistAnalysisUseCase:
    def setup_method(self):
        self.analysis_repo = MagicMock()
        self.analysis_repo.add_analysis = AsyncMock()
        self.analysis_repo.add_alerts = AsyncMock()
        self.analysis_repo.flush = AsyncMock()
        self.analysis_repo.commit = AsyncMock()

        self.wbs_repo = MagicMock()
        self.wbs_repo.bulk_create_from_dicts = AsyncMock()

        self.session = MagicMock()
        self.session.execute = AsyncMock()

        # Patch sqlalchemy.delete to avoid mapper validation on stub ORM
        self._delete_patcher = patch(
            "src.analysis.application.persist_analysis_use_case.delete"
        )
        self.mock_delete = self._delete_patcher.start()
        self.mock_delete.return_value.where.return_value = "mock_delete_stmt"

        self.use_case = PersistAnalysisUseCase(
            analysis_repo=self.analysis_repo,
            wbs_repo=self.wbs_repo,
            session=self.session,
        )

    def teardown_method(self):
        self._delete_patcher.stop()

    @pytest.mark.asyncio
    async def test_persist_with_risks_generates_alerts(self):
        cmd = _make_command(
            extracted_risks=[
                {"title": "R1", "category": "LEGAL", "impact": "HIGH"},
                {"title": "R2", "category": "BUDGET", "impact": "MEDIUM"},
            ],
        )
        result = await self.use_case.execute(cmd)

        assert isinstance(result, PersistAnalysisResult)
        assert isinstance(result.analysis_id, UUID)
        self.analysis_repo.add_analysis.assert_called_once()
        self.analysis_repo.add_alerts.assert_called_once()
        self.analysis_repo.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_generated_risk_alerts_include_legacy_message_column(self):
        """Test Suite ID: TS-QA-SWAGGER-ANALYSIS-003."""
        cmd = _make_command(
            extracted_risks=[{"title": "R1", "category": "LEGAL", "impact": "HIGH"}],
        )

        await self.use_case.execute(cmd)

        alerts = self.analysis_repo.add_alerts.call_args.args[0]
        assert alerts[0].message == alerts[0].description

    @pytest.mark.asyncio
    async def test_persist_with_wbs_deletes_and_creates(self):
        cmd = _make_command(
            extracted_wbs=[{"code": "W1"}, {"code": "W2"}],
        )
        result = await self.use_case.execute(cmd)

        assert isinstance(result.analysis_id, UUID)
        self.session.execute.assert_called()
        self.wbs_repo.bulk_create_from_dicts.assert_called_once()

    @pytest.mark.asyncio
    async def test_persist_with_both_risks_and_wbs(self):
        cmd = _make_command(
            extracted_risks=[{"title": "R1", "category": "LEGAL", "impact": "HIGH"}],
            extracted_wbs=[{"code": "W1"}],
        )
        await self.use_case.execute(cmd)

        self.analysis_repo.add_alerts.assert_called_once()
        self.wbs_repo.bulk_create_from_dicts.assert_called_once()
        self.analysis_repo.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_persist_empty_extractions(self):
        cmd = _make_command(extracted_risks=[], extracted_wbs=[])
        result = await self.use_case.execute(cmd)

        assert isinstance(result.analysis_id, UUID)
        self.analysis_repo.add_alerts.assert_not_called()
        self.wbs_repo.bulk_create_from_dicts.assert_not_called()

    @pytest.mark.asyncio
    async def test_analysis_type_risk_when_risks_present(self):
        cmd = _make_command(
            extracted_risks=[{"title": "R1"}],
        )
        await self.use_case.execute(cmd)

        call_args = self.analysis_repo.add_analysis.call_args
        analysis = call_args.args[0]
        assert analysis.analysis_type == AnalysisType.RISK

    @pytest.mark.asyncio
    async def test_analysis_type_schedule_when_only_wbs(self):
        cmd = _make_command(
            extracted_risks=[],
            extracted_wbs=[{"code": "W1"}],
        )
        await self.use_case.execute(cmd)

        call_args = self.analysis_repo.add_analysis.call_args
        analysis = call_args.args[0]
        assert analysis.analysis_type == AnalysisType.SCHEDULE

    @pytest.mark.asyncio
    async def test_analysis_status_completed(self):
        cmd = _make_command()
        await self.use_case.execute(cmd)

        call_args = self.analysis_repo.add_analysis.call_args
        analysis = call_args.args[0]
        assert analysis.status == AnalysisStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_add_analysis_receives_command_tenant_id(self):
        """TS-SEC-APP-TENANT-001: the use case must never let the repository's

        tenant-ownership check be silently skipped. Omitting ``tenant_id``
        was exactly how a prior version of this call site bypassed
        ``SqlAlchemyAnalysisRepository._verify_project_ownership``.
        """
        cmd = _make_command()
        await self.use_case.execute(cmd)

        call_kwargs = self.analysis_repo.add_analysis.call_args.kwargs
        assert call_kwargs.get("tenant_id") == cmd.tenant_id

    @pytest.mark.asyncio
    async def test_add_alerts_receives_command_tenant_id(self):
        """TS-SEC-APP-TENANT-001: alert persistence must carry the same

        mandatory tenant context as analysis persistence.
        """
        cmd = _make_command(
            extracted_risks=[{"title": "R1", "category": "LEGAL", "impact": "HIGH"}],
        )
        await self.use_case.execute(cmd)

        call_kwargs = self.analysis_repo.add_alerts.call_args.kwargs
        assert call_kwargs.get("tenant_id") == cmd.tenant_id
