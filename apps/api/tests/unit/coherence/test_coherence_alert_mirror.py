"""Unit tests for mirroring /evaluate coherence alerts into the alerts table.

The alerts UI lists rows from the ``alerts`` table; before this, /evaluate only
stored alerts inside ``coherence_results.alerts`` (JSON), so the alerts page was
empty while the dashboard showed a non-zero count. These tests pin the mirror
behaviour: prior coherence rows are cleared (idempotent replace) and each alert
is written with mapped severity/type and traceability metadata.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from src.analysis.adapters.persistence.models import Alert as AlertORM
from src.analysis.domain.enums import AlertSeverity, AlertType
from src.coherence.router import _mirror_coherence_alerts_to_alerts_table


class _FakeSession:
    """Minimal async session double: records execute() and add() calls."""

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.executed: list[Any] = []

    async def execute(self, statement: Any) -> None:
        self.executed.append(statement)

    def add(self, obj: Any) -> None:
        self.added.append(obj)


@pytest.mark.asyncio
async def test_mirror_writes_alert_row_with_mapped_fields() -> None:
    project_id = uuid4()
    tenant_id = uuid4()
    evidence = SimpleNamespace(source_clause_id="clause-1", claim="c", quote="q")
    alert = SimpleNamespace(
        severity="critical",
        category="BUDGET",
        rule_id="DET-BUD-SUM",
        message="Budget items sum below contract total",
        evidence=evidence,
    )
    session = _FakeSession()

    await _mirror_coherence_alerts_to_alerts_table(
        db=session, project_id=project_id, tenant_id=tenant_id, alerts=[alert]
    )

    # Prior coherence-sourced rows are cleared first (idempotent replace).
    assert len(session.executed) == 1
    assert len(session.added) == 1
    row = session.added[0]
    assert isinstance(row, AlertORM)
    assert row.project_id == project_id
    assert row.tenant_id == tenant_id
    assert row.analysis_id is None
    assert row.severity == AlertSeverity.CRITICAL
    assert row.alert_type == AlertType.COHERENCE
    assert row.category == "BUDGET"
    assert row.rule_id == "DET-BUD-SUM"
    assert row.message == "Budget items sum below contract total"
    assert row.title == "Budget items sum below contract total"
    assert row.alert_metadata["source"] == "coherence_evaluate"
    assert row.alert_metadata["evidence"]["source_clause_id"] == "clause-1"


@pytest.mark.asyncio
async def test_mirror_unknown_severity_defaults_medium_and_handles_no_evidence() -> None:
    session = _FakeSession()
    alert = SimpleNamespace(
        severity="bogus", category=None, rule_id=None, message="", evidence=None
    )

    await _mirror_coherence_alerts_to_alerts_table(
        db=session, project_id=uuid4(), tenant_id=uuid4(), alerts=[alert]
    )

    row = session.added[0]
    assert row.severity == AlertSeverity.MEDIUM
    assert row.message == "Coherence issue detected."  # empty message -> fallback
    assert row.alert_metadata["evidence"] is None


@pytest.mark.asyncio
async def test_mirror_empty_alerts_still_clears_prior_batch() -> None:
    session = _FakeSession()

    await _mirror_coherence_alerts_to_alerts_table(
        db=session, project_id=uuid4(), tenant_id=uuid4(), alerts=[]
    )

    # The delete runs even with no new alerts, so a project that no longer has
    # any incoherence ends up with an empty alerts list rather than stale rows.
    assert len(session.executed) == 1
    assert session.added == []
