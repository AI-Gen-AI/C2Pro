"""Unit tests for Journey Excel export builder (WP JV1-A19).

Verifies the generation of journey.xlsx with openpyxl:
- Three sheets: Summary, Findings, Gaps & References.
- Summary sheet: Global Score, 6 subscores, N4 coverage status and metrics.
- Findings sheet: Title, AI Interpretation (labeled), Exact Quote, Page, Clause, Dimension, Severity, Decision, Reviewer, Date.
- Gaps & References sheet: Gaps with ordinal, failure kind, reason, attempts, pages, resolution; References with target and status.
- Opens cleanly in openpyxl without warnings.
- Gracefully handles empty or partial read models.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime
from uuid import UUID, uuid4

import openpyxl
import pytest

from src.reporting.application.build_journey_export import (
    BuildJourneyExportUseCase,
    JourneyExportData,
    JourneyFindingRow,
    JourneyGapRow,
    JourneyReferenceRow,
    JourneySummaryData,
    build_journey_excel_bytes,
    build_journey_workbook,
)


def _sample_journey_data() -> JourneyExportData:
    project_id = uuid4()
    now = datetime(2026, 11, 22, 12, 0, 0, tzinfo=UTC)

    summary = JourneySummaryData(
        project_id=project_id,
        project_name="Synthetic Solar Plant Project",
        project_code="SPP-001",
        status="ACTIVE",
        global_score=82.5,
        trusted_score=80.0,
        projected_score=75.0,
        score_reason="Validated score based on confirmed findings",
        sub_scores={
            "SCOPE": 85.0,
            "BUDGET": 70.0,
            "TIME": 90.0,
            "TECHNICAL": 88.0,
            "LEGAL": 78.0,
            "QUALITY": 86.0,
        },
        coverage_status="COMPLETE_WITH_GAPS",
        total_windows=10,
        examined_windows=9,
        gap_windows_count=1,
        generated_at=now,
    )

    findings = [
        JourneyFindingRow(
            finding_id="f-001",
            title="Late Delivery Penalty Cap Exceeded",
            ai_interpretation="Model detects liquidated damages cap exceeding standard EPC 10% threshold",
            exact_quote="Liquidated damages for delay shall not exceed 15% of the Contract Price.",
            page=24,
            clause="Clause 8.4",
            dimension="TIME",
            severity="HIGH",
            decision="CONFIRMED",
            reviewer="Alice Reviewer",
            decided_at=datetime(2026, 11, 22, 10, 30, 0, tzinfo=UTC),
        ),
        JourneyFindingRow(
            finding_id="f-002",
            title="Unilateral Suspension Right",
            ai_interpretation="Owner has right to suspend without cost compensation",
            exact_quote="The Owner may suspend works without adjustment to Contract Price.",
            page="35-36",
            clause="Clause 14.1",
            dimension="LEGAL",
            severity="CRITICAL",
            decision="CORRECTION_PROPOSED",
            reviewer="Bob Manager",
            decided_at="2026-11-22T11:15:00Z",
        ),
    ]

    gaps = [
        JourneyGapRow(
            ordinal=4,
            failure_kind="OUTPUT_TRUNCATED",
            reason="Window token limit reached during parsing",
            attempts=2,
            page_start=40,
            page_end=48,
            resolution="CLOSED_MANUALLY",
            closed_reason="Manual human review verified no material risks in annex",
            closed_by="Alice Reviewer",
            closed_at=datetime(2026, 11, 22, 11, 0, 0, tzinfo=UTC),
        ),
    ]

    references = [
        JourneyReferenceRow(
            source_identifier="Clause 14.1",
            target_reference="Annex B - Schedule of Unit Rates",
            status="UNRESOLVED",
            details="Unit rates referenced in suspension clause are missing from document",
        ),
    ]

    return JourneyExportData(
        summary=summary,
        findings=findings,
        gaps=gaps,
        references=references,
    )


def test_build_journey_workbook_creates_three_required_sheets() -> None:
    data = _sample_journey_data()
    wb = build_journey_workbook(data)

    sheet_names = wb.sheetnames
    assert sheet_names == ["Summary", "Findings", "Gaps & References"]


def test_summary_sheet_contains_scores_subscores_and_coverage() -> None:
    data = _sample_journey_data()
    wb = build_journey_workbook(data)
    ws = wb["Summary"]

    text_values = [str(cell.value) for row in ws.iter_rows() for cell in row if cell.value is not None]

    # Project metadata
    assert "Synthetic Solar Plant Project" in text_values
    assert "SPP-001" in text_values

    # Global scores
    assert any("82.5" in v for v in text_values)
    assert any("80" in v or "80.0" in v for v in text_values)

    # 6 Canonical subscores
    for category in ("SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"):
        assert category in text_values

    # Coverage metrics
    assert "COMPLETE_WITH_GAPS" in text_values
    assert any("10" in v for v in text_values)  # total windows
    assert any("9" in v for v in text_values)   # examined windows


def test_findings_sheet_contains_all_required_columns_and_rows() -> None:
    data = _sample_journey_data()
    wb = build_journey_workbook(data)
    ws = wb["Findings"]

    headers = [cell.value for cell in ws[1] if cell.value is not None]
    # Required columns per plan §5 A19:
    # título, interpretación IA etiquetada, cita exacta, página, cláusula, decisión, revisor, fecha
    header_str = " ".join(str(h).lower() for h in headers)
    assert "title" in header_str or "título" in header_str
    assert "interpretation" in header_str or "ia" in header_str
    assert "quote" in header_str or "cita" in header_str
    assert "page" in header_str or "página" in header_str
    assert "clause" in header_str or "cláusula" in header_str
    assert "decision" in header_str or "decisión" in header_str
    assert "reviewer" in header_str or "revisor" in header_str
    assert "date" in header_str or "fecha" in header_str

    # Values from finding rows
    findings_values = [str(cell.value) for row in ws.iter_rows(min_row=2) for cell in row if cell.value is not None]
    assert "Late Delivery Penalty Cap Exceeded" in findings_values
    assert any("Liquidated damages" in v for v in findings_values)
    assert "Clause 8.4" in findings_values
    assert "CONFIRMED" in findings_values
    assert "Alice Reviewer" in findings_values
    assert "Unilateral Suspension Right" in findings_values
    assert "Clause 14.1" in findings_values
    assert "CORRECTION_PROPOSED" in findings_values
    assert "Bob Manager" in findings_values


def test_gaps_and_references_sheet_contains_both_tables() -> None:
    data = _sample_journey_data()
    wb = build_journey_workbook(data)
    ws = wb["Gaps & References"]

    values = [str(cell.value) for row in ws.iter_rows() for cell in row if cell.value is not None]

    # Gaps content
    assert "OUTPUT_TRUNCATED" in values
    assert "CLOSED_MANUALLY" in values
    assert any("Manual human review" in v for v in values)
    assert "Alice Reviewer" in values

    # References content
    assert "Clause 14.1" in values
    assert any("Annex B" in v for v in values)
    assert "UNRESOLVED" in values


def test_excel_bytes_can_be_reloaded_cleanly_without_warnings() -> None:
    data = _sample_journey_data()
    excel_bytes = build_journey_excel_bytes(data)

    assert isinstance(excel_bytes, bytes)
    assert len(excel_bytes) > 0

    # Reload with openpyxl from buffer
    buffer = io.BytesIO(excel_bytes)
    wb = openpyxl.load_workbook(buffer, read_only=False, data_only=True)

    assert wb.sheetnames == ["Summary", "Findings", "Gaps & References"]
    assert wb["Summary"].max_row >= 5
    assert wb["Findings"].max_row >= 3
    assert wb["Gaps & References"].max_row >= 3


def test_empty_read_models_generate_valid_workbook() -> None:
    project_id = uuid4()
    empty_data = JourneyExportData(
        summary=JourneySummaryData(
            project_id=project_id,
            project_name="Empty Analysis Project",
            project_code=None,
            status="DRAFT",
            global_score=None,
            trusted_score=None,
            projected_score=None,
            score_reason="No analysis completed yet",
            sub_scores={
                "SCOPE": None,
                "BUDGET": None,
                "TIME": None,
                "TECHNICAL": None,
                "LEGAL": None,
                "QUALITY": None,
            },
            coverage_status="INCOMPLETE",
            total_windows=0,
            examined_windows=0,
            gap_windows_count=0,
            generated_at=datetime.now(UTC),
        ),
        findings=[],
        gaps=[],
        references=[],
    )

    excel_bytes = build_journey_excel_bytes(empty_data)
    buffer = io.BytesIO(excel_bytes)
    wb = openpyxl.load_workbook(buffer)

    assert wb.sheetnames == ["Summary", "Findings", "Gaps & References"]
    ws_summary = wb["Summary"]
    summary_text = [str(c.value) for row in ws_summary.iter_rows() for c in row if c.value is not None]
    assert "Empty Analysis Project" in summary_text
    assert any("Not Evaluated" in v or "None" in v or "N/A" in v for v in summary_text)


@pytest.mark.asyncio
async def test_build_journey_export_use_case() -> None:
    data = _sample_journey_data()

    class _MockSources:
        async def load_journey_data(self, project_id: UUID, tenant_id: UUID) -> JourneyExportData:
            return data

    use_case = BuildJourneyExportUseCase(sources=_MockSources())
    raw_bytes = await use_case.execute(project_id=data.summary.project_id, tenant_id=uuid4())

    wb = openpyxl.load_workbook(io.BytesIO(raw_bytes))
    assert wb.sheetnames == ["Summary", "Findings", "Gaps & References"]
