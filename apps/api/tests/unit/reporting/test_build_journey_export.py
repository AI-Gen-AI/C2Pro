from __future__ import annotations

import io
from datetime import UTC, datetime
from typing import Any
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
    _derive_window_run_coverage_status,
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
        trusted_score=None,
        projected_score=None,
        score_reason="Raw coherence score from automated pipeline",
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
        total_review_items_count=2,
        exported_findings_count=2,
        coherence_source_status="AVAILABLE",
        coverage_source_status="AVAILABLE",
        findings_source_status="AVAILABLE",
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

    assert "Synthetic Solar Plant Project" in text_values
    assert "SPP-001" in text_values
    assert any("82.5" in v for v in text_values)
    assert any("Pending A17/A26" in v or "Not Evaluated" in v for v in text_values)

    for category in ("SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"):
        assert category in text_values

    assert "COMPLETE_WITH_GAPS" in text_values
    assert any("10" in v for v in text_values)
    assert any("9" in v for v in text_values)


def test_findings_sheet_contains_all_required_columns_and_rows() -> None:
    data = _sample_journey_data()
    wb = build_journey_workbook(data)
    ws = wb["Findings"]

    headers = [cell.value for cell in ws[1] if cell.value is not None]
    header_str = " ".join(str(h).lower() for h in headers)
    assert "title" in header_str or "título" in header_str
    assert "interpretation" in header_str or "ia" in header_str
    assert "quote" in header_str or "cita" in header_str
    assert "page" in header_str or "página" in header_str
    assert "clause" in header_str or "cláusula" in header_str
    assert "decision" in header_str or "decisión" in header_str
    assert "reviewer" in header_str or "revisor" in header_str
    assert "date" in header_str or "fecha" in header_str

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

    assert "OUTPUT_TRUNCATED" in values
    assert "CLOSED_MANUALLY" in values
    assert any("Manual human review" in v for v in values)
    assert "Alice Reviewer" in values

    assert "Clause 14.1" in values
    assert any("Annex B" in v for v in values)
    assert "UNRESOLVED" in values


def test_excel_bytes_can_be_reloaded_cleanly_without_warnings() -> None:
    data = _sample_journey_data()
    excel_bytes = build_journey_excel_bytes(data)

    assert isinstance(excel_bytes, bytes)
    assert len(excel_bytes) > 0

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
            total_review_items_count=0,
            exported_findings_count=0,
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


def test_formula_injection_prevention_in_all_untrusted_cells() -> None:
    project_id = uuid4()
    malicious_data = JourneyExportData(
        summary=JourneySummaryData(
            project_id=project_id,
            project_name="=1+1",
            project_code="+SUM(A1:B2)",
            status="@ADMIN",
            global_score=None,
            trusted_score=None,
            projected_score=None,
            score_reason="-danger",
            sub_scores=dict.fromkeys(("SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"), None),
            coverage_status="COMPLETE",
            total_windows=1,
            examined_windows=1,
            gap_windows_count=0,
            generated_at=datetime.now(UTC),
        ),
        findings=[
            JourneyFindingRow(
                finding_id="f-inj-1",
                title="=cmd|'/C calc'!A0",
                ai_interpretation="+2+2",
                exact_quote="-3*3",
                page="@12",
                clause="=HYPERLINK(\"http://evil.com\")",
                dimension="BUDGET",
                severity="HIGH",
                decision="@CONFIRMED",
                reviewer="+Bob",
                decided_at="-2026-11-22",
            )
        ],
        gaps=[
            JourneyGapRow(
                ordinal=1,
                failure_kind="=MALICIOUS_KIND",
                reason="+formula_reason",
                attempts=1,
                page_start=None,
                page_end=None,
                resolution="@OPEN",
                closed_reason="-closed_formula",
                closed_by="+Alice",
                closed_at="=NOW()",
            )
        ],
        references=[
            JourneyReferenceRow(
                source_identifier="=SourceClause",
                target_reference="+TargetDoc",
                status="@UNRESOLVED",
                details="-detail_formula",
            )
        ],
    )

    wb = build_journey_workbook(malicious_data)
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is not None:
                    assert cell.data_type != "f", (
                        f"Formula injection found on sheet '{sheet_name}', cell {cell.coordinate}: "
                        f"value={cell.value!r}, data_type={cell.data_type!r}"
                    )


class _MockQueryResult:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self._rows = rows or []

    def mappings(self) -> _MockQueryResult:
        return self

    def one_or_none(self) -> dict[str, Any] | None:
        return self._rows[0] if self._rows else None

    def all(self) -> list[dict[str, Any]]:
        return self._rows


@pytest.mark.asyncio
async def test_sqlalchemy_journey_sources_full_data_and_a1_a7_contract() -> None:
    project_id = uuid4()
    tenant_id = uuid4()
    run_id = uuid4()
    finding_id = uuid4()

    class _MockAsyncSession:
        async def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _MockQueryResult:
            sql = str(statement)
            if "FROM public.projects" in sql:
                return _MockQueryResult([
                    {"id": project_id, "name": "Wind Farm Beta", "code": "WFB-02", "status": "ACTIVE"}
                ])
            if "FROM public.coherence_results" in sql:
                return _MockQueryResult([
                    {
                        "global_score": 88.0,
                        "category_scores": {
                            "SCOPE": 90.0,
                            "BUDGET": 85.0,
                            "TIME": 82.0,
                            "TECHNICAL": 91.0,
                            "LEGAL": 80.0,
                            "QUALITY": 89.0,
                        },
                        "score_reason": "High coherence validated",
                    }
                ])
            if "FROM public.document_revisions" in sql:
                return _MockQueryResult([
                    {
                        "id": uuid4(),
                        "document_id": uuid4(),
                        "document_metadata": {
                            "analysis_n4_run_id": str(run_id),
                            "analysis_n4_coverage": {
                                "status": "COMPLETE_WITH_GAPS",
                                "total_windows": 10,
                                "examined_windows": 9,
                                "gap_windows": [4],
                                "gaps": [
                                    {
                                        "ordinal": 4,
                                        "failure_kind": "OUTPUT_TRUNCATED",
                                        "reason": "Token budget hit",
                                        "attempts": 2,
                                        "page_start": 40,
                                        "page_end": 45,
                                        "resolution": "CLOSED_MANUALLY",
                                        "closed_reason": "Audited manually",
                                        "closed_by": "QA Reviewer",
                                        "closed_at": "2026-11-22T12:00:00Z",
                                    }
                                ],
                            },
                        },
                    }
                ])
            if "SELECT COUNT(*)" in sql:
                return _MockQueryResult([{"total_count": 3}])
            if "FROM public.hitl_finding_decisions" in sql:
                return _MockQueryResult([
                    {
                        "finding_id": str(finding_id),
                        "action": "CONFIRMED",
                        "reviewer_id": "Lead Auditor",
                        "recorded_at": datetime(2026, 11, 22, 14, 0, 0, tzinfo=UTC),
                    }
                ])
            if "FROM public.review_items" in sql:
                return _MockQueryResult([
                    {
                        "id": finding_id,
                        "current_status": "PROPOSED",
                        "approved_by": None,
                        "approved_at": None,
                        "item_data": {
                            "title": "A1 Conforming Finding",
                            "risk_reason": "Liquidated damages cap exceeded",
                            "source_quote": "Damages capped at 20%",
                            "page_start": 12,
                            "page_end": 14,
                            "clause_ref": "Clause 8.2",
                            "dimension": "BUDGET",
                            "severity_proposed": "CRITICAL",
                            "reference_register": [
                                {
                                    "proposal": "Clause 8.2",
                                    "label": "Annex A - Penalty Matrix",
                                    "status": "IN_DOCUMENT",
                                    "source_quote": "refer to Annex A",
                                    "finding_keys": ["fk-1"],
                                }
                            ],
                        },
                    },
                    {
                        "id": uuid4(),
                        "current_status": "PROPOSED",
                        "approved_by": None,
                        "approved_at": None,
                        "item_data": {
                            "title": "Single Page Finding",
                            "risk_reason": "Single page issue",
                            "source_quote": "Single quote",
                            "page_start": 5,
                            "page_end": None,
                        },
                    },
                    {
                        "id": uuid4(),
                        "current_status": "ESCALATED",
                        "approved_by": None,
                        "approved_at": None,
                        "item_data": {
                            "title": "Legacy Page Finding",
                            "risk_reason": "Legacy page property",
                            "source_quote": "Legacy quote",
                            "page_number": 9,
                        },
                    },
                ])
            return _MockQueryResult()

    from src.reporting.application.build_journey_export import SqlAlchemyJourneyExportSources

    sources = SqlAlchemyJourneyExportSources(session=_MockAsyncSession())  # type: ignore[arg-type]
    data = await sources.load_journey_data(project_id, tenant_id)

    assert data.summary.project_name == "Wind Farm Beta"
    assert data.summary.project_code == "WFB-02"
    assert data.summary.global_score == 88.0
    assert data.summary.trusted_score is None
    assert data.summary.projected_score is None
    assert data.summary.coverage_status == "COMPLETE_WITH_GAPS"
    assert len(data.findings) == 3
    assert data.findings[0].decision == "CONFIRMED"
    assert data.findings[0].reviewer == "Lead Auditor"
    assert data.findings[0].page == "pp. 12–14"
    assert data.findings[0].severity == "CRITICAL"
    assert data.findings[1].page == "p. 5"
    assert data.findings[2].page == 9
    assert len(data.gaps) >= 1
    assert len(data.references) >= 1
    assert data.references[0].target_reference == "Annex A - Penalty Matrix"
    assert data.references[0].status == "IN_DOCUMENT"


@pytest.mark.asyncio
async def test_sqlalchemy_journey_sources_fallback_to_analyses_when_coherence_results_absent() -> None:
    project_id = uuid4()
    tenant_id = uuid4()

    class _MockAsyncSession:
        async def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _MockQueryResult:
            sql = str(statement)
            if "FROM public.projects" in sql:
                return _MockQueryResult([
                    {"id": project_id, "name": "Hydro Plant Delta", "code": None, "status": "DRAFT"}
                ])
            if "FROM public.coherence_results" in sql:
                return _MockQueryResult([])
            if "FROM public.analyses" in sql:
                return _MockQueryResult([
                    {
                        "coherence_score": 74.5,
                        "coherence_breakdown": {"SCOPE": 78.0, "TIME": 71.0},
                    }
                ])
            if "FROM public.document_revisions" in sql:
                return _MockQueryResult([])
            if "FROM public.n4_extraction_runs" in sql:
                return _MockQueryResult([
                    {"run_id": uuid4(), "status": "COMPLETE", "total_windows": 1}
                ])
            if "FROM public.n4_extraction_windows" in sql:
                return _MockQueryResult([
                    {"ordinal": 0, "status": "EXAMINED", "blocked_reason": None, "unresolved_refs": None}
                ])
            return _MockQueryResult([])

    from src.reporting.application.build_journey_export import SqlAlchemyJourneyExportSources

    sources = SqlAlchemyJourneyExportSources(session=_MockAsyncSession())  # type: ignore[arg-type]
    data = await sources.load_journey_data(project_id, tenant_id)

    assert data.summary.project_name == "Hydro Plant Delta"
    assert data.summary.project_code is None
    assert data.summary.global_score == 74.5
    assert data.summary.trusted_score is None
    assert data.summary.sub_scores["SCOPE"] == 78.0
    assert data.summary.coverage_status == "COMPLETE"
    assert data.findings == []
    assert data.gaps == []


@pytest.mark.asyncio
async def test_sqlalchemy_journey_sources_resilient_to_query_exceptions() -> None:
    project_id = uuid4()
    tenant_id = uuid4()

    class _FailingSession:
        async def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _MockQueryResult:
            sql = str(statement)
            if "FROM public.projects" in sql:
                return _MockQueryResult([
                    {"id": project_id, "name": "Resilient Plant", "code": "RP-1", "status": "ACTIVE"}
                ])
            raise RuntimeError("Database connection interrupted")

    from src.reporting.application.build_journey_export import SqlAlchemyJourneyExportSources

    sources = SqlAlchemyJourneyExportSources(session=_FailingSession())  # type: ignore[arg-type]
    data = await sources.load_journey_data(project_id, tenant_id)

    assert data.summary.project_name == "Resilient Plant"
    assert data.summary.global_score is None
    assert data.summary.coherence_source_status == "ERROR"
    assert data.summary.coverage_source_status == "ERROR"
    assert data.summary.findings_source_status == "ERROR"
    assert data.summary.coverage_status == "INCOMPLETE"
    assert data.findings == []


def test_build_journey_workbook_formatting_branches() -> None:
    project_id = uuid4()
    now = datetime(2026, 11, 22, 12, 0, 0, tzinfo=UTC)

    data = JourneyExportData(
        summary=JourneySummaryData(
            project_id=project_id,
            project_name="Branch Test Project",
            project_code="BTP-01",
            status="ACTIVE",
            global_score=None,
            trusted_score=None,
            projected_score=None,
            score_reason=None,
            sub_scores=dict.fromkeys(("SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"), None),
            coverage_status="COMPLETE",
            total_windows=3,
            examined_windows=3,
            gap_windows_count=0,
            generated_at=now,
            total_review_items_count=10,
            exported_findings_count=1,
        ),
        findings=[
            JourneyFindingRow(
                finding_id="f-branch-1",
                title="Already Labeled Finding",
                ai_interpretation="[IA Proposal] Already labeled proposal text",
                exact_quote="Source quote here",
                page="p. 15",
                clause=None,
                dimension=None,
                severity=None,
                decision="PENDING",
                reviewer=None,
                decided_at=None,
            )
        ],
        gaps=[
            JourneyGapRow(
                ordinal=1,
                failure_kind="PROVIDER_REJECTED",
                reason="Transient refusal",
                attempts=1,
                page_start=15,
                page_end=None,
                resolution="OPEN",
                closed_reason=None,
                closed_by=None,
                closed_at=None,
            ),
            JourneyGapRow(
                ordinal=2,
                failure_kind="INVALID_ENVELOPE",
                reason="Schema error",
                attempts=None,
                page_start=None,
                page_end=None,
                resolution="OPEN",
                closed_reason=None,
                closed_by=None,
                closed_at=None,
            ),
        ],
        references=[],
    )

    wb = build_journey_workbook(data)
    assert wb.sheetnames == ["Summary", "Findings", "Gaps & References"]
    ws_findings = wb["Findings"]
    finding_texts = [str(c.value) for row in ws_findings.iter_rows() for c in row if c.value is not None]
    assert any("Showing 1 of 10" in t for t in finding_texts)

    ws_gaps = wb["Gaps & References"]
    gap_values = [str(cell.value) for row in ws_gaps.iter_rows() for cell in row if cell.value is not None]
    assert "p. 15" in gap_values
    assert "Unmapped" in gap_values
    assert "Unknown" in gap_values


@pytest.mark.asyncio
async def test_n4_coverage_fallback_status_partial_not_complete() -> None:
    project_id = uuid4()
    tenant_id = uuid4()
    run_id = uuid4()

    class _MockAsyncSession:
        async def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _MockQueryResult:
            sql = str(statement)
            if "FROM public.projects" in sql:
                return _MockQueryResult([{"id": project_id, "name": "Partial Run Project", "code": "PRP", "status": "ACTIVE"}])
            if "FROM public.coherence_results" in sql:
                return _MockQueryResult([])
            if "FROM public.document_revisions" in sql:
                return _MockQueryResult([])
            if "FROM public.n4_extraction_runs" in sql:
                return _MockQueryResult([{"run_id": run_id, "status": "PARTIAL", "total_windows": 2}])
            if "FROM public.n4_extraction_windows" in sql:
                return _MockQueryResult([
                    {"ordinal": 0, "status": "EXAMINED", "blocked_reason": None, "unresolved_refs": None},
                    {"ordinal": 1, "status": "EXAMINED", "blocked_reason": None, "unresolved_refs": None},
                ])
            return _MockQueryResult([])

    from src.reporting.application.build_journey_export import SqlAlchemyJourneyExportSources
    sources = SqlAlchemyJourneyExportSources(session=_MockAsyncSession())  # type: ignore[arg-type]
    data = await sources.load_journey_data(project_id, tenant_id)

    assert data.summary.coverage_status == "PARTIAL"
    assert data.summary.coverage_status != "COMPLETE"


def test_source_status_error_and_unavailable_visible_in_workbook() -> None:
    project_id = uuid4()
    data = JourneyExportData(
        summary=JourneySummaryData(
            project_id=project_id,
            project_name="Error Sources Project",
            project_code="ESP-1",
            status="ACTIVE",
            global_score=None,
            trusted_score=None,
            projected_score=None,
            score_reason="Database timeout during coherence evaluation",
            sub_scores=dict.fromkeys(("SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"), None),
            coverage_status="INCOMPLETE",
            total_windows=0,
            examined_windows=0,
            gap_windows_count=0,
            generated_at=datetime.now(UTC),
            coherence_source_status="ERROR",
            coverage_source_status="UNAVAILABLE",
            findings_source_status="ERROR",
        ),
        findings=[],
        gaps=[],
        references=[],
    )

    wb = build_journey_workbook(data)

    ws_summary = wb["Summary"]
    summary_text = [str(c.value) for row in ws_summary.iter_rows() for c in row if c.value is not None]
    assert any("[ERROR]" in t for t in summary_text), "Summary sheet must explicitly indicate [ERROR] source status"
    assert any("[UNAVAILABLE]" in t for t in summary_text), "Summary sheet must explicitly indicate [UNAVAILABLE] source status"

    ws_findings = wb["Findings"]
    findings_text = [str(c.value) for row in ws_findings.iter_rows() for c in row if c.value is not None]
    assert not any(t == "No findings recorded for this project." for t in findings_text), "Findings must not claim no findings when there is an error"
    assert any("[ERROR]" in t for t in findings_text), "Findings sheet must explicitly indicate [ERROR] source status"

    ws_gaps = wb["Gaps & References"]
    gaps_text = [str(c.value) for row in ws_gaps.iter_rows() for c in row if c.value is not None]
    assert any("[UNAVAILABLE]" in t for t in gaps_text), "Gaps sheet must explicitly indicate [UNAVAILABLE] source status"


@pytest.mark.asyncio
async def test_pagination_fetches_multiple_batches() -> None:
    project_id = uuid4()
    tenant_id = uuid4()

    class _MockPagedSession:
        async def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _MockQueryResult:
            sql = str(statement)
            if "FROM public.projects" in sql:
                return _MockQueryResult([{"id": project_id, "name": "Paged Project", "code": "PP", "status": "ACTIVE"}])
            if "FROM public.coherence_results" in sql:
                return _MockQueryResult([])
            if "FROM public.document_revisions" in sql:
                return _MockQueryResult([])
            if "FROM public.n4_extraction_runs" in sql:
                return _MockQueryResult([])
            if "SELECT COUNT(*)" in sql:
                return _MockQueryResult([{"total_count": 600}])
            if "FROM public.hitl_finding_decisions" in sql:
                return _MockQueryResult([])
            if "FROM public.review_items" in sql:
                offset = params.get("offset", 0) if params else 0
                if offset == 0:
                    # First page of 500 items
                    return _MockQueryResult([{"id": uuid4(), "current_status": "PROPOSED", "item_data": {"title": f"F-{i}"}} for i in range(500)])
                elif offset == 500:
                    # Second page of 100 items
                    return _MockQueryResult([{"id": uuid4(), "current_status": "PROPOSED", "item_data": {"title": f"F-{500+i}"}} for i in range(100)])
                return _MockQueryResult([])
            return _MockQueryResult([])

    from src.reporting.application.build_journey_export import SqlAlchemyJourneyExportSources
    sources = SqlAlchemyJourneyExportSources(session=_MockPagedSession())  # type: ignore[arg-type]
    data = await sources.load_journey_data(project_id, tenant_id)

    assert data.summary.total_review_items_count == 600
    assert data.summary.exported_findings_count == 600
    assert len(data.findings) == 600


@pytest.mark.parametrize(
    ("total_w", "seen_ordinals", "exam_w", "gap_count", "non_terminal", "unknown_count", "run_status", "expected"),
    [
        # 1. PARTIAL + BLOCKED -> PARTIAL (never COMPLETE_WITH_GAPS!)
        (2, {0, 1}, 1, 1, 0, 0, "PARTIAL", "PARTIAL"),
        # 2. PARTIAL + EXAMINED -> PARTIAL (never COMPLETE!)
        (2, {0, 1}, 2, 0, 0, 0, "PARTIAL", "PARTIAL"),
        # 3. PARTIAL + PENDING -> PARTIAL
        (2, {0, 1}, 1, 0, 1, 0, "PARTIAL", "PARTIAL"),
        # 4. Run terminal + missing ordinal (0, 2 present; 1 missing) -> INCOMPLETE
        (3, {0, 2}, 1, 1, 0, 0, "COMPLETE", "INCOMPLETE"),
        # 5. Examined + Blocked + Pending -> INCOMPLETE
        (3, {0, 1, 2}, 1, 1, 1, 0, "COMPLETE", "INCOMPLETE"),
        # 6. Unknown run status -> INCOMPLETE
        (2, {0, 1}, 2, 0, 0, 0, "UNKNOWN_STATUS", "INCOMPLETE"),
        # 7. Unknown window status -> INCOMPLETE
        (2, {0, 1}, 1, 0, 0, 1, "COMPLETE", "INCOMPLETE"),
        # 8. Valid terminal COMPLETE (all examined, no gaps) -> COMPLETE
        (2, {0, 1}, 2, 0, 0, 0, "COMPLETE", "COMPLETE"),
        # 9. Valid terminal COMPLETE_WITH_GAPS (all accounted, gaps > 0) -> COMPLETE_WITH_GAPS
        (2, {0, 1}, 1, 1, 0, 0, "COMPLETE", "COMPLETE_WITH_GAPS"),
    ],
)
def test_derive_window_run_coverage_status_parametrized_failclosed(
    total_w: int,
    seen_ordinals: set[int],
    exam_w: int,
    gap_count: int,
    non_terminal: int,
    unknown_count: int,
    run_status: str,
    expected: str,
) -> None:
    result = _derive_window_run_coverage_status(
        total_w=total_w,
        seen_ordinals=seen_ordinals,
        exam_w=exam_w,
        gap_count=gap_count,
        non_terminal_count=non_terminal,
        unknown_status_count=unknown_count,
        run_status=run_status,
    )
    assert result == expected


@pytest.mark.asyncio
async def test_n4_coverage_failclosed_partial_plus_blocked_end_to_end() -> None:
    """End-to-end: run_status PARTIAL with gap window must return PARTIAL, not COMPLETE_WITH_GAPS."""
    project_id = uuid4()
    tenant_id = uuid4()
    run_id = uuid4()

    class _MockSession:
        async def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _MockQueryResult:
            sql = str(statement)
            if "FROM public.projects" in sql:
                return _MockQueryResult([{"id": project_id, "name": "P+B Project", "code": "PB", "status": "ACTIVE"}])
            if "FROM public.coherence_results" in sql:
                return _MockQueryResult([])
            if "FROM public.document_revisions" in sql:
                return _MockQueryResult([])
            if "FROM public.n4_extraction_runs" in sql:
                return _MockQueryResult([{"run_id": run_id, "status": "PARTIAL", "total_windows": 2}])
            if "FROM public.n4_extraction_windows" in sql:
                return _MockQueryResult([
                    {"ordinal": 0, "status": "EXAMINED", "blocked_reason": None, "unresolved_refs": None},
                    {"ordinal": 1, "status": "BLOCKED", "blocked_reason": "OUTPUT_TRUNCATED", "unresolved_refs": None},
                ])
            return _MockQueryResult([])

    from src.reporting.application.build_journey_export import SqlAlchemyJourneyExportSources
    sources = SqlAlchemyJourneyExportSources(session=_MockSession())  # type: ignore[arg-type]
    data = await sources.load_journey_data(project_id, tenant_id)

    assert data.summary.coverage_status == "PARTIAL"
    assert data.summary.coverage_status != "COMPLETE_WITH_GAPS"
    assert data.summary.coverage_status != "COMPLETE"


@pytest.mark.asyncio
async def test_n4_coverage_failclosed_terminal_run_with_missing_ordinal() -> None:
    """End-to-end: run_status COMPLETE but ordinal 1 missing out of total 3 -> INCOMPLETE."""
    project_id = uuid4()
    tenant_id = uuid4()
    run_id = uuid4()

    class _MockSession:
        async def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _MockQueryResult:
            sql = str(statement)
            if "FROM public.projects" in sql:
                return _MockQueryResult([{"id": project_id, "name": "Missing Ordinal Project", "code": "MO", "status": "ACTIVE"}])
            if "FROM public.coherence_results" in sql:
                return _MockQueryResult([])
            if "FROM public.document_revisions" in sql:
                return _MockQueryResult([])
            if "FROM public.n4_extraction_runs" in sql:
                return _MockQueryResult([{"run_id": run_id, "status": "COMPLETE", "total_windows": 3}])
            if "FROM public.n4_extraction_windows" in sql:
                # Ordinals 0 and 2 are present, but ordinal 1 is missing
                return _MockQueryResult([
                    {"ordinal": 0, "status": "EXAMINED", "blocked_reason": None, "unresolved_refs": None},
                    {"ordinal": 2, "status": "BLOCKED", "blocked_reason": "OUTPUT_TRUNCATED", "unresolved_refs": None},
                ])
            return _MockQueryResult([])

    from src.reporting.application.build_journey_export import SqlAlchemyJourneyExportSources
    sources = SqlAlchemyJourneyExportSources(session=_MockSession())  # type: ignore[arg-type]
    data = await sources.load_journey_data(project_id, tenant_id)

    assert data.summary.coverage_status == "INCOMPLETE"


@pytest.mark.asyncio
async def test_n4_coverage_failclosed_terminal_run_with_pending_window() -> None:
    """End-to-end: run_status COMPLETE but window 2 is PENDING -> INCOMPLETE."""
    project_id = uuid4()
    tenant_id = uuid4()
    run_id = uuid4()

    class _MockSession:
        async def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _MockQueryResult:
            sql = str(statement)
            if "FROM public.projects" in sql:
                return _MockQueryResult([{"id": project_id, "name": "Pending Window Project", "code": "PW", "status": "ACTIVE"}])
            if "FROM public.coherence_results" in sql:
                return _MockQueryResult([])
            if "FROM public.document_revisions" in sql:
                return _MockQueryResult([])
            if "FROM public.n4_extraction_runs" in sql:
                return _MockQueryResult([{"run_id": run_id, "status": "COMPLETE", "total_windows": 3}])
            if "FROM public.n4_extraction_windows" in sql:
                return _MockQueryResult([
                    {"ordinal": 0, "status": "EXAMINED", "blocked_reason": None, "unresolved_refs": None},
                    {"ordinal": 1, "status": "BLOCKED", "blocked_reason": "OUTPUT_TRUNCATED", "unresolved_refs": None},
                    {"ordinal": 2, "status": "PENDING", "blocked_reason": None, "unresolved_refs": None},
                ])
            return _MockQueryResult([])

    from src.reporting.application.build_journey_export import SqlAlchemyJourneyExportSources
    sources = SqlAlchemyJourneyExportSources(session=_MockSession())  # type: ignore[arg-type]
    data = await sources.load_journey_data(project_id, tenant_id)

    assert data.summary.coverage_status == "INCOMPLETE"


# JV1 L6: regression/negative tests for exact-SHA review observations.
@pytest.mark.asyncio
async def test_sql_backed_unavailable_is_distinct_from_sql_error_and_empty_findings() -> None:
    """No coherence or N4 rows after tenant-scoped SQL => UNAVAILABLE, not ERROR/AVAILABLE."""
    from src.reporting.application.build_journey_export import SqlAlchemyJourneyExportSources

    project_id = uuid4()
    tenant_id = uuid4()
    observed: list[tuple[str, dict[str, Any]]] = []

    class _NoSourceRowsSession:
        async def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _MockQueryResult:
            sql = str(statement)
            bound = dict(params or {})
            observed.append((sql, bound))
            assert bound.get("tenant_id") == str(tenant_id), "all reads must be tenant-scoped"
            if "FROM public.projects" in sql:
                return _MockQueryResult([
                    {"id": project_id, "name": "Synthetic SQL Missing Sources", "code": "SS-1", "status": "ACTIVE"}
                ])
            if "SELECT COUNT(*)" in sql:
                return _MockQueryResult([{"total_count": 0}])
            return _MockQueryResult([])

    sources = SqlAlchemyJourneyExportSources(session=_NoSourceRowsSession())  # type: ignore[arg-type]
    data = await sources.load_journey_data(project_id, tenant_id)
    assert data.summary.coherence_source_status == "UNAVAILABLE"
    assert data.summary.coverage_source_status == "UNAVAILABLE"
    assert data.summary.findings_source_status == "AVAILABLE"  # SQL proved count=0
    assert data.summary.coverage_status == "INCOMPLETE"
    assert data.summary.global_score is None
    assert data.summary.trusted_score is None
    assert data.summary.projected_score is None
    assert any("FROM public.coherence_results" in s for s, _ in observed)
    assert any("FROM public.analyses" in s for s, _ in observed)
    assert any("FROM public.n4_extraction_runs" in s for s, _ in observed)

    wb = build_journey_workbook(data)
    summary_text = [str(c.value) for row in wb["Summary"].iter_rows() for c in row if c.value is not None]
    gaps_text = [str(c.value) for row in wb["Gaps & References"].iter_rows() for c in row if c.value is not None]
    assert any("[UNAVAILABLE] No coherence evaluation" in item for item in summary_text)
    assert any("[UNAVAILABLE] No N4 extraction run" in item for item in summary_text)
    assert any("[UNAVAILABLE] No N4 extraction run" in item for item in gaps_text)
    assert not any("[ERROR]" in item for item in summary_text)


@pytest.mark.asyncio
async def test_review_pagination_uses_unique_id_tiebreaker_for_identical_timestamps() -> None:
    """Two pages sharing created_at must have a total unique order, not SQL-dependent ties."""
    from src.reporting.application.build_journey_export import SqlAlchemyJourneyExportSources

    project_id, tenant_id = uuid4(), uuid4()
    created_at = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
    rows = [
        {"id": UUID(int=i + 1), "current_status": "PROPOSED",
         "item_data": {"title": f"F-{i}"}, "created_at": created_at}
        for i in reversed(range(501))
    ]
    observed_offsets: list[int] = []

    class _TiedTimestampRows:
        async def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _MockQueryResult:
            sql = str(statement)
            assert "ORDER BY created_at ASC, id ASC" in sql, "id is required for deterministic tie ordering"
            assert params and params["tenant_id"] == str(tenant_id)
            offset, limit = int(params["offset"]), int(params["limit"])
            observed_offsets.append(offset)
            ordered = sorted(rows, key=lambda r: (r["created_at"], r["id"]))
            return _MockQueryResult(ordered[offset:offset + limit])

    sources = SqlAlchemyJourneyExportSources(session=_TiedTimestampRows())  # type: ignore[arg-type]
    fetched = await sources._fetch_review_items_paginated(project_id, tenant_id)
    ids = [r["id"] for r in fetched]
    assert len(ids) == 501 and len(set(ids)) == 501
    assert ids == sorted(ids)
    assert observed_offsets == [0, 500]


@pytest.mark.parametrize(
    ("raw", "total", "expected"),
    [
        (None, 3, None), (True, 3, None), (False, 3, None),
        (-1, 3, None), (3, 3, None), (1000, 3, None),
        ("bad", 3, None), ("1.5", 3, None), ("-1", 3, None),
        (0, 3, 0), (1, 3, 1), ("2", 3, 2),
    ],
)
def test_invalid_window_ordinal_never_aliases_real_window_zero(
    raw: Any, total: int, expected: int | None
) -> None:
    from src.reporting.application.build_journey_export import _validated_window_ordinal

    assert _validated_window_ordinal(raw, total) == expected


def test_bad_sql_window_ordinal_remains_unknown_in_gap_and_reference_exports() -> None:
    from dataclasses import replace

    from src.reporting.application.build_journey_export import _parse_windows_for_run

    status, exam, count, gaps, references = _parse_windows_for_run(
        [
            {"ordinal": 0, "status": "EXAMINED", "unresolved_refs": None},
            {"ordinal": "not-an-ordinal", "status": "BLOCKED", "blocked_reason": "TOKEN_LIMIT",
             "unresolved_refs": ["Annex Z"]},
        ], total_w=2, run_status="COMPLETE"
    )
    assert status == "INCOMPLETE"
    assert exam == 1 and count == 1
    assert len(gaps) == 1 and gaps[0].ordinal is None
    assert references[0].source_identifier == "Window Unknown"
    book = build_journey_workbook(replace(_sample_journey_data(), gaps=gaps))
    assert book["Gaps & References"]["A3"].value == "Unknown (invalid ordinal)"


def test_invalid_metadata_gap_ordinal_downgrades_claim_of_complete_coverage() -> None:
    from src.reporting.application.build_journey_export import _parse_metadata_coverage

    parsed = _parse_metadata_coverage({
        "analysis_n4_coverage": {
            "status": "COMPLETE_WITH_GAPS",
            "total_windows": 2,
            "examined_windows": 1,
            "gap_windows": ["invalid"],
            "gaps": [{"ordinal": "not-an-ordinal", "failure_kind": "BLOCKED", "reason": "No page"}],
        }
    })
    assert parsed is not None
    status, total, examined, gap_count, gaps = parsed
    assert (status, total, examined, gap_count) == ("INCOMPLETE", 2, 1, 1)
    assert len(gaps) == 1 and gaps[0].ordinal is None
