"""TS-P0D-REPORT-004 - Build Journey Excel Export (WP JV1-A19).

Generates journey.xlsx with openpyxl:
- Hojas Summary (Score, 6 subscores, cobertura), Findings (título, interpretación
  IA etiquetada, cita exacta, página, cláusula, decisión, revisor, fecha),
  Gaps & References.
- Valores derivados exclusivamente de modelos de lectura (read models).
- Validación de aislamiento multi-tenant y apertura sin advertencias en Excel.
- Defensas contra inyección de fórmulas (CSV/Excel Formula Injection).
- Interoperabilidad con contratos congelados A1 y A7 sin asumir A7 fusionado.
- Clasificación limpia de calidad Sonar (sin duplicación ni complejidad cognitiva excesiva).
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

import openpyxl
import structlog
from openpyxl.cell import Cell
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

CANONICAL_DIMENSIONS: tuple[str, ...] = (
    "SCOPE",
    "BUDGET",
    "TIME",
    "TECHNICAL",
    "LEGAL",
    "QUALITY",
)

DIMENSION_WEIGHTS: dict[str, float] = {
    "SCOPE": 0.20,
    "BUDGET": 0.20,
    "TIME": 0.15,
    "TECHNICAL": 0.15,
    "LEGAL": 0.15,
    "QUALITY": 0.15,
}

FORMULA_PREFIXES: tuple[str, ...] = ("=", "+", "-", "@", "\t", "\r")


@dataclass(frozen=True)
class JourneySummaryData:
    project_id: UUID
    project_name: str
    project_code: str | None
    status: str
    global_score: float | None
    trusted_score: float | None
    projected_score: float | None
    score_reason: str | None
    sub_scores: dict[str, float | None]
    coverage_status: str | None
    total_windows: int
    examined_windows: int
    gap_windows_count: int
    generated_at: datetime
    total_review_items_count: int = 0
    exported_findings_count: int = 0
    coherence_source_status: str = "AVAILABLE"
    coverage_source_status: str = "AVAILABLE"
    findings_source_status: str = "AVAILABLE"


@dataclass(frozen=True)
class JourneyFindingRow:
    finding_id: str | None
    title: str
    ai_interpretation: str
    exact_quote: str
    page: str | int | None
    clause: str | None
    dimension: str | None
    severity: str | None
    decision: str
    reviewer: str | None
    decided_at: datetime | str | None


@dataclass(frozen=True)
class JourneyGapRow:
    ordinal: int
    failure_kind: str
    reason: str
    attempts: int | None
    page_start: int | None
    page_end: int | None
    resolution: str
    closed_reason: str | None
    closed_by: str | None
    closed_at: datetime | str | None


@dataclass(frozen=True)
class JourneyReferenceRow:
    source_identifier: str
    target_reference: str
    status: str
    details: str | None


@dataclass(frozen=True)
class JourneyExportData:
    summary: JourneySummaryData
    findings: list[JourneyFindingRow]
    gaps: list[JourneyGapRow]
    references: list[JourneyReferenceRow]


class JourneyExportSources(Protocol):
    async def load_journey_data(self, project_id: UUID, tenant_id: UUID) -> JourneyExportData: ...


def safe_set_cell_value(cell: Cell, val: Any) -> None:
    """Set cell value safely ensuring untrusted text cannot trigger spreadsheet formula injection.

    Prepends a single quote and sets data_type to string if the value starts with formula
    triggers (=, +, -, @, \t, \r). Numbers, booleans, and None are passed as-is.
    """
    if val is None:
        cell.value = None
        return
    if isinstance(val, (int, float, bool)):
        cell.value = val
        return
    if isinstance(val, datetime):
        cell.value = val.strftime("%Y-%m-%d %H:%M UTC")
        cell.data_type = "s"
        return

    text_str = str(val)
    if text_str.startswith(FORMULA_PREFIXES):
        cell.data_type = "s"
        cell.value = "'" + text_str
    else:
        cell.data_type = "s"
        cell.value = text_str


def _format_date(val: datetime | str | None) -> str:
    if val is None:
        return "N/A"
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M UTC")
    return str(val)


def _format_score(val: float | None) -> str | float:
    if val is None:
        return "Not Evaluated"
    return round(float(val), 1)


def _format_gap_page_range(start: int | None, end: int | None) -> str:
    """Format page span without nested ternary conditionals (Sonar S3358)."""
    if start is not None and end is not None:
        return f"pp. {start}–{end}"
    if start is not None:
        return f"p. {start}"
    return "Unmapped"


class _ReportStyles:
    def __init__(self) -> None:
        self.font_title = Font(name="Calibri", size=14, bold=True, color="1F4E78")
        self.font_section = Font(name="Calibri", size=12, bold=True, color="1F4E78")
        self.font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        self.font_bold = Font(name="Calibri", size=11, bold=True)
        self.font_regular = Font(name="Calibri", size=11)
        self.font_italic = Font(name="Calibri", size=10, italic=True, color="595959")
        self.font_alert = Font(name="Calibri", size=10, italic=True, color="C00000")

        self.fill_header_navy = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        self.fill_header_dark = PatternFill(start_color="2E4053", end_color="2E4053", fill_type="solid")
        self.fill_zebra = PatternFill(start_color="F2F4F7", end_color="F2F4F7", fill_type="solid")

        thin_side = Side(style="thin", color="D9D9D9")
        self.border_thin = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

        self.align_center = Alignment(horizontal="center", vertical="center")
        self.align_left = Alignment(horizontal="left", vertical="center")
        self.align_wrap = Alignment(horizontal="left", vertical="top", wrap_text=True)


def _render_summary_sheet(ws: Worksheet, summary: JourneySummaryData, styles: _ReportStyles) -> None:
    ws.title = "Summary"
    ws.views.sheetView[0].showGridLines = True

    # Title Block
    safe_set_cell_value(ws.cell(row=1, column=1), "C2Pro Journey V1 - Project Summary Report")
    ws.cell(row=1, column=1).font = styles.font_title

    meta_items: list[tuple[str, Any]] = [
        ("Project Name", summary.project_name),
        ("Project Code", summary.project_code or "N/A"),
        ("Project ID", str(summary.project_id)),
        ("Project Status", summary.status),
        ("Report Generated At", _format_date(summary.generated_at)),
    ]
    curr_row = 3
    for label, meta_val in meta_items:
        c_lbl = ws.cell(row=curr_row, column=1)
        safe_set_cell_value(c_lbl, label)
        c_lbl.font = styles.font_bold

        c_val = ws.cell(row=curr_row, column=2)
        safe_set_cell_value(c_val, meta_val)
        c_val.font = styles.font_regular
        curr_row += 1

    # Section 1: Scores Overview
    curr_row += 1
    safe_set_cell_value(ws.cell(row=curr_row, column=1), "Coherence Score Overview")
    ws.cell(row=curr_row, column=1).font = styles.font_section
    curr_row += 1

    for col_idx, h in enumerate(["Metric", "Value", "Description"], start=1):
        cell = ws.cell(row=curr_row, column=col_idx)
        safe_set_cell_value(cell, h)
        cell.font = styles.font_header
        cell.fill = styles.fill_header_navy
        cell.alignment = styles.align_left
        cell.border = styles.border_thin
    curr_row += 1

    # P0: Do NOT label raw global_score as validated. A17/A26 are not merged.
    validated_label = "Not Evaluated (Pending A17/A26 Integration)" if summary.trusted_score is None else _format_score(summary.trusted_score)
    projected_label = "Not Evaluated (Pending A17/A26 Integration)" if summary.projected_score is None else _format_score(summary.projected_score)
    reason_label = summary.score_reason or "Pending dual score reconciliation (A17/A26)"

    score_rows: list[tuple[str, Any, str]] = [
        ("Global Coherence Score", _format_score(summary.global_score), "Consolidated raw project coherence indicator"),
        ("Validated Score (Trusted)", validated_label, "Requires dual score & HITL reconciliation (A17/A26 DEPENDENCY_HOLD)"),
        ("Projected Score", projected_label, "Adjusted score based on pending findings (A17/A26 DEPENDENCY_HOLD)"),
        ("Score Reason / Evaluation State", reason_label, "Current evaluation status"),
    ]
    for metric, score_val, desc in score_rows:
        c1 = ws.cell(row=curr_row, column=1)
        c2 = ws.cell(row=curr_row, column=2)
        c3 = ws.cell(row=curr_row, column=3)
        safe_set_cell_value(c1, metric)
        safe_set_cell_value(c2, score_val)
        safe_set_cell_value(c3, desc)
        for c in (c1, c2, c3):
            c.font = styles.font_regular
            c.border = styles.border_thin
        curr_row += 1

    # Section 2: Canonical Subscores
    curr_row += 1
    safe_set_cell_value(ws.cell(row=curr_row, column=1), "Canonical Dimensions (6 Subscores)")
    ws.cell(row=curr_row, column=1).font = styles.font_section
    curr_row += 1

    for col_idx, h in enumerate(["Dimension", "Weight", "Score", "Evaluation Status"], start=1):
        cell = ws.cell(row=curr_row, column=col_idx)
        safe_set_cell_value(cell, h)
        cell.font = styles.font_header
        cell.fill = styles.fill_header_navy
        cell.alignment = styles.align_left
        cell.border = styles.border_thin
    curr_row += 1

    for dim in CANONICAL_DIMENSIONS:
        weight_pct = f"{int(DIMENSION_WEIGHTS.get(dim, 0.15) * 100)}%"
        sub_val = summary.sub_scores.get(dim)
        eval_status = "Assessed" if sub_val is not None else "Not Evaluated"
        c1 = ws.cell(row=curr_row, column=1)
        c2 = ws.cell(row=curr_row, column=2)
        c3 = ws.cell(row=curr_row, column=3)
        c4 = ws.cell(row=curr_row, column=4)
        safe_set_cell_value(c1, dim)
        safe_set_cell_value(c2, weight_pct)
        safe_set_cell_value(c3, _format_score(sub_val))
        safe_set_cell_value(c4, eval_status)
        for c in (c1, c2, c3, c4):
            c.font = styles.font_regular
            c.border = styles.border_thin
        curr_row += 1

    # Section 3: Coverage N4
    curr_row += 1
    safe_set_cell_value(ws.cell(row=curr_row, column=1), "Contract Analysis Coverage (N4)")
    ws.cell(row=curr_row, column=1).font = styles.font_section
    curr_row += 1

    for col_idx, h in enumerate(["Coverage Metric", "Value"], start=1):
        cell = ws.cell(row=curr_row, column=col_idx)
        safe_set_cell_value(cell, h)
        cell.font = styles.font_header
        cell.fill = styles.fill_header_navy
        cell.alignment = styles.align_left
        cell.border = styles.border_thin
    curr_row += 1

    total_w = summary.total_windows
    exam_w = summary.examined_windows
    gap_w = summary.gap_windows_count
    cov_pct = f"{round((exam_w / total_w) * 100, 1)}%" if total_w > 0 else "0.0%"

    cov_rows: list[tuple[str, Any]] = [
        ("N4 Coverage Status", summary.coverage_status or "INCOMPLETE"),
        ("Total Contract Windows", total_w),
        ("Examined Windows", exam_w),
        ("Gap Windows", gap_w),
        ("Examined Window Ratio", cov_pct),
        ("Findings Exported", f"{summary.exported_findings_count} of {summary.total_review_items_count} recorded items"),
    ]
    for cov_metric, cov_val in cov_rows:
        c1 = ws.cell(row=curr_row, column=1)
        c2 = ws.cell(row=curr_row, column=2)
        safe_set_cell_value(c1, cov_metric)
        safe_set_cell_value(c2, cov_val)
        for c in (c1, c2):
            c.font = styles.font_regular
            c.border = styles.border_thin
        curr_row += 1


def _render_findings_sheet(ws: Worksheet, findings: list[JourneyFindingRow], summary: JourneySummaryData, styles: _ReportStyles) -> None:
    ws.title = "Findings"
    ws.views.sheetView[0].showGridLines = True

    finding_headers = [
        "Title",
        "AI Interpretation [IA Proposal]",
        "Exact Source Quote",
        "Page",
        "Clause",
        "Dimension",
        "Severity",
        "Human Decision",
        "Reviewer",
        "Decision Date",
    ]
    for col_idx, h in enumerate(finding_headers, start=1):
        cell = ws.cell(row=1, column=col_idx)
        safe_set_cell_value(cell, h)
        cell.font = styles.font_header
        cell.fill = styles.fill_header_dark
        cell.alignment = styles.align_center
        cell.border = styles.border_thin

    if summary.total_review_items_count > summary.exported_findings_count:
        cell_warn = ws.cell(row=2, column=1)
        safe_set_cell_value(cell_warn, f"[NOTICE] Showing {summary.exported_findings_count} of {summary.total_review_items_count} findings recorded for this project (batch ceiling reached).")
        cell_warn.font = styles.font_alert
        start_row = 3
    else:
        start_row = 2

    if not findings:
        cell_empty = ws.cell(row=start_row, column=1)
        safe_set_cell_value(cell_empty, "No findings recorded for this project.")
        cell_empty.font = styles.font_italic
        return

    for idx, f in enumerate(findings):
        row_idx = start_row + idx
        interpretation = f.ai_interpretation.strip()
        if interpretation and not interpretation.startswith("[IA Proposal]"):
            interpretation = f"[IA Proposal] {interpretation}"

        page_val = str(f.page) if f.page is not None else "Unspecified"
        row_data: list[Any] = [
            f.title,
            interpretation or "[IA Proposal] None",
            f.exact_quote,
            page_val,
            f.clause or "Unspecified",
            f.dimension or "Unassigned",
            f.severity or "Unassessed",
            f.decision,
            f.reviewer or "Unassigned",
            _format_date(f.decided_at),
        ]
        fill = styles.fill_zebra if row_idx % 2 == 1 else None
        for col_idx, val in enumerate(row_data, start=1):
            cell = ws.cell(row=row_idx, column=col_idx)
            safe_set_cell_value(cell, val)
            cell.font = styles.font_regular
            cell.border = styles.border_thin
            cell.alignment = styles.align_wrap if col_idx in (1, 2, 3) else styles.align_center
            if fill:
                cell.fill = fill


def _render_gaps_sheet(ws: Worksheet, gaps: list[JourneyGapRow], references: list[JourneyReferenceRow], styles: _ReportStyles) -> None:
    ws.title = "Gaps & References"
    ws.views.sheetView[0].showGridLines = True

    # Part A: Gaps
    safe_set_cell_value(ws.cell(row=1, column=1), "N4 Contract Coverage Gaps")
    ws.cell(row=1, column=1).font = styles.font_section

    gap_headers = [
        "Window Ordinal",
        "Failure Kind",
        "Failure Reason",
        "Attempts",
        "Page Range",
        "Resolution Status",
        "Closed Reason",
        "Closed By",
        "Closed Date",
    ]
    for col_idx, h in enumerate(gap_headers, start=1):
        cell = ws.cell(row=2, column=col_idx)
        safe_set_cell_value(cell, h)
        cell.font = styles.font_header
        cell.fill = styles.fill_header_dark
        cell.alignment = styles.align_center
        cell.border = styles.border_thin

    gap_row_idx = 3
    if not gaps:
        cell_no_gaps = ws.cell(row=gap_row_idx, column=1)
        safe_set_cell_value(cell_no_gaps, "No coverage gaps recorded (full window coverage or no analysis).")
        cell_no_gaps.font = styles.font_italic
        gap_row_idx += 1
    else:
        for g in gaps:
            pages = _format_gap_page_range(g.page_start, g.page_end)
            attempts_val = g.attempts if g.attempts is not None else "Unknown"
            g_vals: list[Any] = [
                g.ordinal,
                g.failure_kind,
                g.reason,
                attempts_val,
                pages,
                g.resolution,
                g.closed_reason or "N/A",
                g.closed_by or "N/A",
                _format_date(g.closed_at),
            ]
            fill = styles.fill_zebra if gap_row_idx % 2 == 1 else None
            for col_idx, gap_val in enumerate(g_vals, start=1):
                cell = ws.cell(row=gap_row_idx, column=col_idx)
                safe_set_cell_value(cell, gap_val)
                cell.font = styles.font_regular
                cell.border = styles.border_thin
                cell.alignment = styles.align_center if col_idx in (1, 2, 4, 5, 6, 8, 9) else styles.align_wrap
                if fill:
                    cell.fill = fill
            gap_row_idx += 1

    # Part B: References / Remisiones (A7 Reference Register)
    gap_row_idx += 2
    safe_set_cell_value(ws.cell(row=gap_row_idx, column=1), "Cross-Document References & Remisiones")
    ws.cell(row=gap_row_idx, column=1).font = styles.font_section
    gap_row_idx += 1

    ref_headers = [
        "Source Element / Proposal",
        "Target Reference (Remisión / Label)",
        "Resolution Status",
        "Details / Context Quote",
    ]
    for col_idx, h in enumerate(ref_headers, start=1):
        cell = ws.cell(row=gap_row_idx, column=col_idx)
        safe_set_cell_value(cell, h)
        cell.font = styles.font_header
        cell.fill = styles.fill_header_dark
        cell.alignment = styles.align_center
        cell.border = styles.border_thin
    gap_row_idx += 1

    if not references:
        cell_no_refs = ws.cell(row=gap_row_idx, column=1)
        safe_set_cell_value(cell_no_refs, "No contract references or remisiones recorded.")
        cell_no_refs.font = styles.font_italic
    else:
        for r in references:
            r_vals: list[Any] = [
                r.source_identifier,
                r.target_reference,
                r.status,
                r.details or "N/A",
            ]
            fill = styles.fill_zebra if gap_row_idx % 2 == 1 else None
            for col_idx, ref_val in enumerate(r_vals, start=1):
                cell = ws.cell(row=gap_row_idx, column=col_idx)
                safe_set_cell_value(cell, ref_val)
                cell.font = styles.font_regular
                cell.border = styles.border_thin
                cell.alignment = styles.align_center if col_idx == 3 else styles.align_wrap
                if fill:
                    cell.fill = fill
            gap_row_idx += 1


def _auto_fit_columns(worksheets: Sequence[Worksheet]) -> None:
    for ws in worksheets:
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                if cell.value is not None:
                    for line in str(cell.value).split("\n"):
                        max_len = max(max_len, len(line))
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 65)


def build_journey_workbook(data: JourneyExportData) -> openpyxl.Workbook:
    """Generate a clean, warning-free openpyxl workbook with 3 required sheets."""
    wb = openpyxl.Workbook()
    styles = _ReportStyles()

    ws_summary = wb.active
    _render_summary_sheet(ws_summary, data.summary, styles)

    ws_findings = wb.create_sheet(title="Findings")
    _render_findings_sheet(ws_findings, data.findings, data.summary, styles)

    ws_gaps = wb.create_sheet(title="Gaps & References")
    _render_gaps_sheet(ws_gaps, data.gaps, data.references, styles)

    _auto_fit_columns((ws_summary, ws_findings, ws_gaps))
    return wb


def build_journey_excel_bytes(data: JourneyExportData) -> bytes:
    """Build and serialize openpyxl workbook to bytes."""
    wb = build_journey_workbook(data)
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


class SqlAlchemyJourneyExportSources:
    """Read model sources backed by SQLAlchemy session and tenant boundary."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _load_project_identity(self, project_id: UUID, tenant_id: UUID) -> tuple[str, str | None, str]:
        row = (await self._session.execute(text("""
            SELECT id, name, code, status
              FROM public.projects
             WHERE id = CAST(:project_id AS uuid)
               AND tenant_id = CAST(:tenant_id AS uuid)
        """), {"project_id": str(project_id), "tenant_id": str(tenant_id)})).mappings().one_or_none()

        proj_name = str(row["name"]) if row and row.get("name") else "Project"
        proj_code = str(row["code"]) if row and row.get("code") else None
        proj_status = str(row["status"]) if row and row.get("status") else "UNKNOWN"
        return proj_name, proj_code, proj_status

    async def _load_coherence_scores(
        self, project_id: UUID, tenant_id: UUID
    ) -> tuple[float | None, str | None, dict[str, float | None], str]:
        global_score: float | None = None
        score_reason: str | None = None
        sub_scores: dict[str, float | None] = dict.fromkeys(CANONICAL_DIMENSIONS, None)
        source_status = "AVAILABLE"

        try:
            coh_row = (await self._session.execute(text("""
                SELECT global_score, category_scores, score_reason
                  FROM public.coherence_results
                 WHERE project_id = CAST(:project_id AS uuid)
                   AND tenant_id = CAST(:tenant_id AS uuid)
                 ORDER BY calculated_at DESC
                 LIMIT 1
            """), {"project_id": str(project_id), "tenant_id": str(tenant_id)})).mappings().one_or_none()

            if coh_row is not None:
                if coh_row.get("global_score") is not None:
                    global_score = float(coh_row["global_score"])
                score_reason = coh_row.get("score_reason")
                cats = coh_row.get("category_scores")
                if isinstance(cats, dict):
                    for k, v in cats.items():
                        norm_k = str(k).upper()
                        if norm_k in sub_scores:
                            sub_scores[norm_k] = float(v) if v is not None else None
            else:
                an_row = (await self._session.execute(text("""
                    SELECT coherence_score, coherence_breakdown
                      FROM public.analyses
                     WHERE project_id = CAST(:project_id AS uuid)
                       AND tenant_id = CAST(:tenant_id AS uuid)
                       AND status = 'COMPLETED'
                     ORDER BY completed_at DESC NULLS LAST, created_at DESC
                     LIMIT 1
                """), {"project_id": str(project_id), "tenant_id": str(tenant_id)})).mappings().one_or_none()
                if an_row is not None and an_row.get("coherence_score") is not None:
                    global_score = float(an_row["coherence_score"])
                    breakdown = an_row.get("coherence_breakdown")
                    if isinstance(breakdown, dict):
                        for k, v in breakdown.items():
                            norm_k = str(k).upper()
                            if norm_k in sub_scores:
                                sub_scores[norm_k] = float(v) if v is not None else None
        except Exception:
            logger.exception("journey_export_coherence_read_failed", project_id=str(project_id))
            source_status = "ERROR"

        return global_score, score_reason, sub_scores, source_status

    async def _load_n4_coverage_and_gaps(
        self, project_id: UUID, tenant_id: UUID
    ) -> tuple[str, int, int, int, list[JourneyGapRow], list[JourneyReferenceRow], str]:
        coverage_status: str = "INCOMPLETE"
        total_windows = 0
        examined_windows = 0
        gap_windows_count = 0
        gaps: list[JourneyGapRow] = []
        references: list[JourneyReferenceRow] = []
        source_status = "AVAILABLE"

        try:
            # Check pinned document revision identity first (P0)
            rev_row = (await self._session.execute(text("""
                SELECT id, document_id, document_metadata
                  FROM public.document_revisions
                 WHERE project_id = CAST(:project_id AS uuid)
                   AND tenant_id = CAST(:tenant_id AS uuid)
                 ORDER BY created_at DESC
                 LIMIT 1
            """), {"project_id": str(project_id), "tenant_id": str(tenant_id)})).mappings().one_or_none()

            raw_meta = rev_row.get("document_metadata") if rev_row else None
            meta: dict[str, Any] = dict(raw_meta) if isinstance(raw_meta, dict) else {}
            pinned_run_id = meta.get("analysis_n4_run_id") or meta.get("n4_run_id")

            # Check if canonical n4_coverage is in metadata
            cov_meta = meta.get("analysis_n4_coverage") or meta.get("n4_coverage")
            if isinstance(cov_meta, dict):
                if cov_meta.get("status"):
                    coverage_status = str(cov_meta["status"])
                if cov_meta.get("total_windows") is not None:
                    total_windows = int(cov_meta["total_windows"])
                if cov_meta.get("examined_windows") is not None:
                    examined_windows = int(cov_meta["examined_windows"])
                if isinstance(cov_meta.get("gap_windows"), Sequence) and not isinstance(cov_meta["gap_windows"], str | bytes):
                    gap_windows_count = len(cov_meta["gap_windows"])
                if isinstance(cov_meta.get("gaps"), Sequence):
                    for g_item in cov_meta["gaps"]:
                        if isinstance(g_item, dict):
                            gaps.append(
                                JourneyGapRow(
                                    ordinal=int(g_item.get("ordinal", 0)),
                                    failure_kind=str(g_item.get("failure_kind") or "UNKNOWN_BLOCK"),
                                    reason=str(g_item.get("reason") or "Window gap"),
                                    attempts=int(g_item["attempts"]) if g_item.get("attempts") is not None else None,
                                    page_start=g_item.get("page_start"),
                                    page_end=g_item.get("page_end"),
                                    resolution=str(g_item.get("resolution") or "OPEN"),
                                    closed_reason=g_item.get("closed_reason"),
                                    closed_by=g_item.get("closed_by"),
                                    closed_at=g_item.get("closed_at"),
                                )
                            )

            # If not already populated from metadata, query runs table pinned to run_id
            if total_windows == 0:
                if pinned_run_id:
                    run_query = text("""
                        SELECT run_id, status, total_windows
                          FROM public.n4_extraction_runs
                         WHERE run_id = CAST(:run_id AS uuid)
                           AND tenant_id = CAST(:tenant_id AS uuid)
                         LIMIT 1
                    """)
                    params = {"run_id": str(pinned_run_id), "tenant_id": str(tenant_id)}
                else:
                    run_query = text("""
                        SELECT run_id, status, total_windows
                          FROM public.n4_extraction_runs
                         WHERE project_id = CAST(:project_id AS uuid)
                           AND tenant_id = CAST(:tenant_id AS uuid)
                         ORDER BY created_at DESC
                         LIMIT 1
                    """)
                    params = {"project_id": str(project_id), "tenant_id": str(tenant_id)}

                run_row = (await self._session.execute(run_query, params)).mappings().one_or_none()
                if run_row is not None:
                    active_run_id = run_row["run_id"]
                    total_windows = int(run_row.get("total_windows") or 0)

                    window_rows = (await self._session.execute(text("""
                        SELECT ordinal, status, blocked_reason, unresolved_refs
                          FROM public.n4_extraction_windows
                         WHERE run_id = CAST(:run_id AS uuid)
                           AND tenant_id = CAST(:tenant_id AS uuid)
                         ORDER BY ordinal
                    """), {"run_id": str(active_run_id), "tenant_id": str(tenant_id)})).mappings().all()

                    for w in window_rows:
                        w_status = str(w.get("status") or "")
                        if w_status == "EXAMINED":
                            examined_windows += 1
                        elif w_status in ("BLOCKED", "FAILED"):
                            gap_windows_count += 1
                            gaps.append(
                                JourneyGapRow(
                                    ordinal=int(w["ordinal"]),
                                    failure_kind=str(w.get("blocked_reason") or "UNKNOWN_BLOCK"),
                                    reason=str(w.get("blocked_reason") or "Window could not be examined"),
                                    attempts=None,
                                    page_start=None,
                                    page_end=None,
                                    resolution="OPEN",
                                    closed_reason=None,
                                    closed_by=None,
                                    closed_at=None,
                                )
                            )

                        unres = w.get("unresolved_refs")
                        if isinstance(unres, Sequence) and not isinstance(unres, str | bytes):
                            for ref in unres:
                                references.append(
                                    JourneyReferenceRow(
                                        source_identifier=f"Window {w['ordinal']}",
                                        target_reference=str(ref),
                                        status="UNRESOLVED",
                                        details="Unresolved reference recorded during extraction",
                                    )
                                )

                    if total_windows > 0 and examined_windows == total_windows:
                        coverage_status = "COMPLETE"
                    elif examined_windows > 0 and gap_windows_count > 0:
                        coverage_status = "COMPLETE_WITH_GAPS"
                    else:
                        coverage_status = "INCOMPLETE"
        except Exception:
            logger.exception("journey_export_n4_read_failed", project_id=str(project_id))
            source_status = "ERROR"

        return coverage_status, total_windows, examined_windows, gap_windows_count, gaps, references, source_status

    async def _load_findings_and_decisions(
        self, project_id: UUID, tenant_id: UUID, references_collector: list[JourneyReferenceRow]
    ) -> tuple[list[JourneyFindingRow], int, int, str]:
        findings: list[JourneyFindingRow] = []
        total_items_count = 0
        source_status = "AVAILABLE"

        try:
            # 1. Total count query (avoids silent omission past ceiling)
            count_row = (await self._session.execute(text("""
                SELECT COUNT(*) AS total_count
                  FROM public.review_items
                 WHERE project_id = CAST(:project_id AS uuid)
                   AND tenant_id = CAST(:tenant_id AS uuid)
            """), {"project_id": str(project_id), "tenant_id": str(tenant_id)})).mappings().one_or_none()
            total_items_count = int(count_row["total_count"]) if count_row and count_row.get("total_count") is not None else 0

            # 2. Query individual decisions from hitl_finding_decisions ledger (P1)
            ledger_rows = (await self._session.execute(text("""
                SELECT DISTINCT ON (finding_id) finding_id, action, reviewer_id, recorded_at
                  FROM public.hitl_finding_decisions
                 WHERE project_id = CAST(:project_id AS uuid)
                   AND tenant_id = CAST(:tenant_id AS uuid)
                 ORDER BY finding_id, recorded_at DESC
            """), {"project_id": str(project_id), "tenant_id": str(tenant_id)})).mappings().all()

            decisions_by_finding: dict[str, dict[str, Any]] = {
                str(row["finding_id"]): dict(row) for row in ledger_rows if row.get("finding_id")
            }

            # 3. Query review items up to batch ceiling
            review_rows = (await self._session.execute(text("""
                SELECT id, current_status, approved_by, approved_at, item_data
                  FROM public.review_items
                 WHERE project_id = CAST(:project_id AS uuid)
                   AND tenant_id = CAST(:tenant_id AS uuid)
                 ORDER BY created_at
                 LIMIT 500
            """), {"project_id": str(project_id), "tenant_id": str(tenant_id)})).mappings().all()

            for r in review_rows:
                item_data = r.get("item_data") or {}
                if not isinstance(item_data, dict):
                    continue

                # Support A7 reference register schema: label, status, source_quote, proposal
                ref_items = (
                    item_data.get("reference_register")
                    or item_data.get("references")
                    or item_data.get("remisiones")
                )
                if isinstance(ref_items, Sequence) and not isinstance(ref_items, str | bytes):
                    for ref_dict in ref_items:
                        if isinstance(ref_dict, dict):
                            references_collector.append(
                                JourneyReferenceRow(
                                    source_identifier=str(ref_dict.get("proposal") or ref_dict.get("source") or ref_dict.get("source_clause") or "Contract Section"),
                                    target_reference=str(ref_dict.get("label") or ref_dict.get("target") or ref_dict.get("target_reference") or "Cross Reference"),
                                    status=str(ref_dict.get("status") or "UNRESOLVED"),
                                    details=str(ref_dict.get("source_quote") or ref_dict.get("details") or ref_dict.get("reason") or ""),
                                )
                            )

                action_item = item_data.get("action_item") or item_data.get("risk") or item_data
                title = str(action_item.get("title") or action_item.get("description") or "Finding")
                interpretation = str(
                    action_item.get("ai_interpretation")
                    or action_item.get("interpretation")
                    or action_item.get("risk_reason")
                    or action_item.get("recommended_action")
                    or ""
                )
                exact_quote = str(
                    action_item.get("exact_quote")
                    or action_item.get("source_quote")
                    or action_item.get("quote")
                    or ""
                )
                p_start = action_item.get("page_start")
                p_end = action_item.get("page_end")
                if p_start is not None and p_end is not None and p_start != p_end:
                    page: str | int | None = f"pp. {p_start}–{p_end}"
                elif p_start is not None:
                    page = f"p. {p_start}"
                else:
                    page = action_item.get("page") or action_item.get("page_number")

                clause = action_item.get("clause") or action_item.get("clause_ref")
                dimension = action_item.get("dimension") or action_item.get("category")
                severity = action_item.get("severity") or action_item.get("severity_proposed") or action_item.get("impact_level")

                # Correlate with individual decision from hitl_finding_decisions ledger (P1)
                finding_str_id = str(r["id"])
                ledger_dec = decisions_by_finding.get(finding_str_id)
                if ledger_dec is not None:
                    decision_val = str(ledger_dec.get("action") or r.get("current_status") or "PROPOSED")
                    reviewer_val = str(ledger_dec.get("reviewer_id")) if ledger_dec.get("reviewer_id") else None
                    decided_at_val = ledger_dec.get("recorded_at") or r.get("approved_at")
                else:
                    decision_val = str(r.get("current_status") or "PROPOSED")
                    reviewer_val = str(r.get("approved_by")) if r.get("approved_by") else None
                    decided_at_val = r.get("approved_at")

                findings.append(
                    JourneyFindingRow(
                        finding_id=finding_str_id,
                        title=title,
                        ai_interpretation=interpretation,
                        exact_quote=exact_quote,
                        page=page,
                        clause=clause,
                        dimension=str(dimension) if dimension else None,
                        severity=str(severity) if severity else None,
                        decision=decision_val,
                        reviewer=reviewer_val,
                        decided_at=decided_at_val,
                    )
                )
        except Exception:
            logger.exception("journey_export_findings_read_failed", project_id=str(project_id))
            source_status = "ERROR"

        exported_count = len(findings)
        if total_items_count == 0:
            total_items_count = exported_count

        return findings, total_items_count, exported_count, source_status

    async def load_journey_data(self, project_id: UUID, tenant_id: UUID) -> JourneyExportData:
        proj_name, proj_code, proj_status = await self._load_project_identity(project_id, tenant_id)
        global_score, score_reason, sub_scores, coh_status = await self._load_coherence_scores(project_id, tenant_id)
        cov_status, total_w, exam_w, gap_w, gaps, references, cov_source_status = await self._load_n4_coverage_and_gaps(project_id, tenant_id)
        findings, total_items, exported_count, findings_status = await self._load_findings_and_decisions(project_id, tenant_id, references)

        # Dual score: trusted_score and projected_score remain None until A17/A26 are integrated
        summary = JourneySummaryData(
            project_id=project_id,
            project_name=proj_name,
            project_code=proj_code,
            status=proj_status,
            global_score=global_score,
            trusted_score=None,
            projected_score=None,
            score_reason=score_reason,
            sub_scores=sub_scores,
            coverage_status=cov_status,
            total_windows=total_w,
            examined_windows=exam_w,
            gap_windows_count=gap_w,
            generated_at=datetime.now(UTC),
            total_review_items_count=total_items,
            exported_findings_count=exported_count,
            coherence_source_status=coh_status,
            coverage_source_status=cov_source_status,
            findings_source_status=findings_status,
        )

        return JourneyExportData(
            summary=summary,
            findings=findings,
            gaps=gaps,
            references=references,
        )


class BuildJourneyExportUseCase:
    """Use case coordinating read models and Excel generation."""

    def __init__(self, sources: JourneyExportSources) -> None:
        self._sources = sources

    async def execute(self, project_id: UUID, tenant_id: UUID) -> bytes:
        data = await self._sources.load_journey_data(project_id, tenant_id)
        return build_journey_excel_bytes(data)


__all__ = [
    "CANONICAL_DIMENSIONS",
    "DIMENSION_WEIGHTS",
    "BuildJourneyExportUseCase",
    "JourneyExportData",
    "JourneyExportSources",
    "JourneyFindingRow",
    "JourneyGapRow",
    "JourneyReferenceRow",
    "JourneySummaryData",
    "SqlAlchemyJourneyExportSources",
    "build_journey_excel_bytes",
    "build_journey_workbook",
    "safe_set_cell_value",
]
