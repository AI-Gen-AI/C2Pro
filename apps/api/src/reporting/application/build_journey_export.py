"""TS-P0D-REPORT-004 - Build Journey Excel Export (WP JV1-A19).

Generates journey.xlsx with openpyxl:
- Hojas Summary (Score, 6 subscores, cobertura), Findings (título, interpretación
  IA etiquetada, cita exacta, página, cláusula, decisión, revisor, fecha),
  Gaps & References.
- Valores derivados exclusivamente de modelos de lectura (read models).
- Validación de aislamiento multi-tenant y apertura sin advertencias en Excel.
- Defensas contra inyección de fórmulas (CSV/Excel Formula Injection).
- Interoperabilidad con contratos congelados A1 y A7 sin asumir A7 fusionado.
- Modularidad limpia sin complejidad cognitiva excesiva (Sonar python:S3776).
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
REVIEW_ITEMS_BATCH_SIZE = 500
REVIEW_ITEMS_MAX_EXPORT = 5000


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
    ordinal: int | None  # Preserve missing/invalid source ordinal, never fabricate window 0
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
    """Set cell value safely ensuring untrusted text cannot trigger spreadsheet formula injection."""
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
        self.font_alert = Font(name="Calibri", size=10, bold=True, color="C00000")

        self.fill_header_navy = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        self.fill_header_dark = PatternFill(start_color="2E4053", end_color="2E4053", fill_type="solid")
        self.fill_zebra = PatternFill(start_color="F2F4F7", end_color="F2F4F7", fill_type="solid")

        thin_side = Side(style="thin", color="D9D9D9")
        self.border_thin = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

        self.align_center = Alignment(horizontal="center", vertical="center")
        self.align_left = Alignment(horizontal="left", vertical="center")
        self.align_wrap = Alignment(horizontal="left", vertical="top", wrap_text=True)


# ---------------------------------------------------------------------------
# Section Renderers for Summary Sheet (Decomposed to resolve Sonar S3776)
# ---------------------------------------------------------------------------

def _render_summary_metadata(ws: Worksheet, summary: JourneySummaryData, styles: _ReportStyles) -> int:
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
    return curr_row


def _render_summary_scores(ws: Worksheet, summary: JourneySummaryData, styles: _ReportStyles, start_row: int) -> int:
    curr_row = start_row + 1
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

    validated_label = "Not Evaluated (Pending A17/A26 Integration)" if summary.trusted_score is None else _format_score(summary.trusted_score)
    projected_label = "Not Evaluated (Pending A17/A26 Integration)" if summary.projected_score is None else _format_score(summary.projected_score)
    reason_label = summary.score_reason or "Pending dual score reconciliation (A17/A26)"

    score_rows: list[tuple[str, Any, str]] = [
        ("Global Coherence Score", _format_score(summary.global_score), "Consolidated raw project coherence indicator"),
        ("Validated Score (Trusted)", validated_label, "Requires dual score & HITL reconciliation (A17/A26 DEPENDENCY_HOLD)"),
        ("Projected Score", projected_label, "Adjusted score based on pending findings (A17/A26 DEPENDENCY_HOLD)"),
        ("Score Reason / Evaluation State", reason_label, "Current evaluation status"),
    ]

    # Explicitly render source status if error or unavailable
    if summary.coherence_source_status in ("ERROR", "UNAVAILABLE"):
        score_rows.append((
            "Coherence Data Source Status",
            ("[UNAVAILABLE] No coherence evaluation recorded in queried SQL sources"
             if summary.coherence_source_status == "UNAVAILABLE"
             else "[ERROR] Coherence evaluation SQL read failed"),
            "Recorded data absence or SQL read failure (distinct states)",
        ))

    for metric, score_val, desc in score_rows:
        c1 = ws.cell(row=curr_row, column=1)
        c2 = ws.cell(row=curr_row, column=2)
        c3 = ws.cell(row=curr_row, column=3)
        safe_set_cell_value(c1, metric)
        safe_set_cell_value(c2, score_val)
        safe_set_cell_value(c3, desc)
        for c in (c1, c2, c3):
            c.font = styles.font_alert if "Source Status" in metric else styles.font_regular
            c.border = styles.border_thin
        curr_row += 1
    return curr_row


def _render_summary_subscores(ws: Worksheet, sub_scores: dict[str, float | None], styles: _ReportStyles, start_row: int) -> int:
    curr_row = start_row + 1
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
        sub_val = sub_scores.get(dim)
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
    return curr_row


def _render_summary_coverage(ws: Worksheet, summary: JourneySummaryData, styles: _ReportStyles, start_row: int) -> int:
    curr_row = start_row + 1
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
    cov_pct = f"{round((exam_w / total_w) * 100, 1)}%" if total_w > 0 else "Not Evaluated"

    cov_rows: list[tuple[str, Any]] = [
        ("N4 Coverage Status", summary.coverage_status or "INCOMPLETE"),
        ("Total Contract Windows", total_w),
        ("Examined Windows", exam_w),
        ("Gap Windows", gap_w),
        ("Examined Window Ratio", cov_pct),
        ("Findings Exported", f"{summary.exported_findings_count} of {summary.total_review_items_count} recorded items"),
    ]

    if summary.coverage_source_status in ("ERROR", "UNAVAILABLE"):
        cov_rows.append((
            "Contract Analysis Source Status",
            ("[UNAVAILABLE] No N4 extraction run recorded in queried SQL sources"
             if summary.coverage_source_status == "UNAVAILABLE"
             else "[ERROR] N4 coverage SQL read failed"),
        ))

    if summary.findings_source_status in ("ERROR", "UNAVAILABLE"):
        cov_rows.append((
            "Findings Data Source Status",
            f"[{summary.findings_source_status}] Review items could not be retrieved",
        ))

    for cov_metric, cov_val in cov_rows:
        c1 = ws.cell(row=curr_row, column=1)
        c2 = ws.cell(row=curr_row, column=2)
        safe_set_cell_value(c1, cov_metric)
        safe_set_cell_value(c2, cov_val)
        for c in (c1, c2):
            c.font = styles.font_alert if "Source Status" in cov_metric else styles.font_regular
            c.border = styles.border_thin
        curr_row += 1
    return curr_row


def _render_summary_sheet(ws: Worksheet, summary: JourneySummaryData, styles: _ReportStyles) -> None:
    ws.title = "Summary"
    ws.views.sheetView[0].showGridLines = True
    row = _render_summary_metadata(ws, summary, styles)
    row = _render_summary_scores(ws, summary, styles, row)
    row = _render_summary_subscores(ws, summary.sub_scores, styles, row)
    _render_summary_coverage(ws, summary, styles, row)


# ---------------------------------------------------------------------------
# Section Renderers for Findings Sheet (Decomposed to resolve Sonar S3776)
# ---------------------------------------------------------------------------

def _render_findings_header(ws: Worksheet, styles: _ReportStyles) -> None:
    headers = [
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
    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx)
        safe_set_cell_value(cell, h)
        cell.font = styles.font_header
        cell.fill = styles.fill_header_dark
        cell.alignment = styles.align_center
        cell.border = styles.border_thin


def _render_single_finding_row(ws: Worksheet, row_idx: int, f: JourneyFindingRow, fill: PatternFill | None, styles: _ReportStyles) -> None:
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
    for col_idx, val in enumerate(row_data, start=1):
        cell = ws.cell(row=row_idx, column=col_idx)
        safe_set_cell_value(cell, val)
        cell.font = styles.font_regular
        cell.border = styles.border_thin
        cell.alignment = styles.align_wrap if col_idx in (1, 2, 3) else styles.align_center
        if fill:
            cell.fill = fill


def _render_findings_sheet(ws: Worksheet, findings: list[JourneyFindingRow], summary: JourneySummaryData, styles: _ReportStyles) -> None:
    ws.title = "Findings"
    ws.views.sheetView[0].showGridLines = True
    _render_findings_header(ws, styles)

    start_row = 2
    if summary.total_review_items_count > summary.exported_findings_count:
        cell_warn = ws.cell(row=2, column=1)
        safe_set_cell_value(cell_warn, f"[NOTICE] Showing {summary.exported_findings_count} of {summary.total_review_items_count} findings recorded for this project (maximum export limit reached).")
        cell_warn.font = styles.font_alert
        start_row = 3

    if summary.findings_source_status in ("ERROR", "UNAVAILABLE"):
        cell_err = ws.cell(row=start_row, column=1)
        safe_set_cell_value(cell_err, f"[{summary.findings_source_status}] Unable to load findings due to data source error.")
        cell_err.font = styles.font_alert
        return

    if not findings:
        cell_empty = ws.cell(row=start_row, column=1)
        safe_set_cell_value(cell_empty, "No findings recorded for this project.")
        cell_empty.font = styles.font_italic
        return

    for idx, f in enumerate(findings):
        row_idx = start_row + idx
        fill = styles.fill_zebra if row_idx % 2 == 1 else None
        _render_single_finding_row(ws, row_idx, f, fill, styles)


# ---------------------------------------------------------------------------
# Section Renderers for Gaps Sheet (Decomposed to resolve Sonar S3776)
# ---------------------------------------------------------------------------

def _render_gaps_table(ws: Worksheet, gaps: list[JourneyGapRow], cov_source_status: str, styles: _ReportStyles) -> int:
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
    if cov_source_status in ("ERROR", "UNAVAILABLE"):
        cell_err = ws.cell(row=gap_row_idx, column=1)
        message = (
            "[UNAVAILABLE] No N4 extraction run exists for the selected revision"
            if cov_source_status == "UNAVAILABLE"
            else "[ERROR] N4 coverage SQL read failed"
        )
        safe_set_cell_value(cell_err, message)
        cell_err.font = styles.font_alert
        return gap_row_idx + 1

    if not gaps:
        cell_no_gaps = ws.cell(row=gap_row_idx, column=1)
        safe_set_cell_value(cell_no_gaps, "No coverage gaps recorded (full window coverage or no analysis).")
        cell_no_gaps.font = styles.font_italic
        return gap_row_idx + 1

    for g in gaps:
        pages = _format_gap_page_range(g.page_start, g.page_end)
        attempts_val = g.attempts if g.attempts is not None else "Unknown"
        g_vals: list[Any] = [
            g.ordinal if g.ordinal is not None else "Unknown (invalid ordinal)",
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
    return gap_row_idx


def _render_references_table(ws: Worksheet, references: list[JourneyReferenceRow], styles: _ReportStyles, start_row: int) -> None:
    curr_row = start_row + 1
    safe_set_cell_value(ws.cell(row=curr_row, column=1), "Cross-Document References & Remisiones")
    ws.cell(row=curr_row, column=1).font = styles.font_section
    curr_row += 1

    ref_headers = [
        "Source Element / Proposal",
        "Target Reference (Remisión / Label)",
        "Resolution Status",
        "Details / Context Quote",
    ]
    for col_idx, h in enumerate(ref_headers, start=1):
        cell = ws.cell(row=curr_row, column=col_idx)
        safe_set_cell_value(cell, h)
        cell.font = styles.font_header
        cell.fill = styles.fill_header_dark
        cell.alignment = styles.align_center
        cell.border = styles.border_thin
    curr_row += 1

    if not references:
        cell_no_refs = ws.cell(row=curr_row, column=1)
        safe_set_cell_value(cell_no_refs, "No contract references or remisiones recorded.")
        cell_no_refs.font = styles.font_italic
        return

    for r in references:
        r_vals: list[Any] = [
            r.source_identifier,
            r.target_reference,
            r.status,
            r.details or "N/A",
        ]
        fill = styles.fill_zebra if curr_row % 2 == 1 else None
        for col_idx, ref_val in enumerate(r_vals, start=1):
            cell = ws.cell(row=curr_row, column=col_idx)
            safe_set_cell_value(cell, ref_val)
            cell.font = styles.font_regular
            cell.border = styles.border_thin
            cell.alignment = styles.align_center if col_idx == 3 else styles.align_wrap
            if fill:
                cell.fill = fill
        curr_row += 1


def _render_gaps_sheet(ws: Worksheet, gaps: list[JourneyGapRow], references: list[JourneyReferenceRow], cov_source_status: str, styles: _ReportStyles) -> None:
    ws.title = "Gaps & References"
    ws.views.sheetView[0].showGridLines = True
    next_row = _render_gaps_table(ws, gaps, cov_source_status, styles)
    _render_references_table(ws, references, styles, next_row)


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
    _render_gaps_sheet(ws_gaps, data.gaps, data.references, data.summary.coverage_source_status, styles)

    _auto_fit_columns((ws_summary, ws_findings, ws_gaps))
    return wb


def build_journey_excel_bytes(data: JourneyExportData) -> bytes:
    """Build and serialize openpyxl workbook to bytes."""
    wb = build_journey_workbook(data)
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Domain Loaders for SqlAlchemyJourneyExportSources (Sonar S3776 Refactoring)
# ---------------------------------------------------------------------------

def _extract_coherence_result(coh_row: Any, sub_scores: dict[str, float | None]) -> tuple[float | None, str | None]:
    global_score: float | None = None
    if coh_row.get("global_score") is not None:
        global_score = float(coh_row["global_score"])
    score_reason = coh_row.get("score_reason")
    cats = coh_row.get("category_scores")
    if isinstance(cats, dict):
        for k, v in cats.items():
            norm_k = str(k).upper()
            if norm_k in sub_scores:
                sub_scores[norm_k] = float(v) if v is not None else None
    return global_score, score_reason


def _extract_analysis_fallback(an_row: Any, sub_scores: dict[str, float | None]) -> float | None:
    global_score: float | None = None
    if an_row.get("coherence_score") is not None:
        global_score = float(an_row["coherence_score"])
        breakdown = an_row.get("coherence_breakdown")
        if isinstance(breakdown, dict):
            for k, v in breakdown.items():
                norm_k = str(k).upper()
                if norm_k in sub_scores:
                    sub_scores[norm_k] = float(v) if v is not None else None
    return global_score


def _validated_window_ordinal(raw: Any, total_windows: int) -> int | None:
    """Return a real in-range ordinal or None; do not invent window zero."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        ordinal = raw
    elif isinstance(raw, str) and raw.isascii() and raw.isdecimal():
        # Guard against oversized untrusted numeric strings (Python int digit limit).
        if len(raw) > 20:
            return None
        ordinal = int(raw)
    else:
        return None
    return ordinal if 0 <= ordinal < total_windows else None


def _parse_metadata_coverage(meta: dict[str, Any]) -> tuple[str, int, int, int, list[JourneyGapRow]] | None:
    cov_meta = meta.get("analysis_n4_coverage") or meta.get("n4_coverage")
    if not isinstance(cov_meta, dict):
        return None

    cov_status = str(cov_meta.get("status") or "INCOMPLETE")
    total_w = int(cov_meta.get("total_windows") or 0)
    exam_w = int(cov_meta.get("examined_windows") or 0)
    gap_count = len(cov_meta["gap_windows"]) if isinstance(cov_meta.get("gap_windows"), Sequence) and not isinstance(cov_meta["gap_windows"], str | bytes) else 0

    gaps: list[JourneyGapRow] = []
    if isinstance(cov_meta.get("gaps"), Sequence):
        for g_item in cov_meta["gaps"]:
            if isinstance(g_item, dict):
                ordinal = _validated_window_ordinal(g_item.get("ordinal"), total_w)
                if ordinal is None:
                    cov_status = "INCOMPLETE"  # invalid metadata cannot attest complete coverage
                gaps.append(
                    JourneyGapRow(
                        ordinal=ordinal,
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
    return cov_status, total_w, exam_w, gap_count, gaps


TERMINAL_RUN_STATUSES: frozenset[str] = frozenset({"COMPLETE", "COMPLETED", "SUCCEEDED"})
TERMINAL_GAP_STATUSES: frozenset[str] = frozenset({"BLOCKED", "FAILED"})
NON_TERMINAL_WINDOW_STATUSES: frozenset[str] = frozenset({"PENDING", "IN_PROGRESS", "UNEXAMINED", "CLAIMED", "QUEUED"})


def _derive_window_run_coverage_status(
    total_w: int,
    seen_ordinals: set[int],
    exam_w: int,
    gap_count: int,
    non_terminal_count: int,
    unknown_status_count: int,
    run_status: str,
) -> str:
    """Determine coverage status fail-closed.

    Rules:
    1. PARTIAL run_status is authoritative and must NEVER be promoted to COMPLETE or COMPLETE_WITH_GAPS.
       Always returns "PARTIAL".
    2. COMPLETE requires:
       - run_status in TERMINAL_RUN_STATUSES
       - total_w > 0
       - seen_ordinals == set(range(total_w)) (no missing or out-of-range ordinals)
       - exam_w == total_w
       - gap_count == 0
       - non_terminal_count == 0
       - unknown_status_count == 0
    3. COMPLETE_WITH_GAPS requires:
       - run_status in TERMINAL_RUN_STATUSES
       - total_w > 0
       - seen_ordinals == set(range(total_w))
       - exam_w > 0
       - gap_count > 0
       - exam_w + gap_count == total_w
       - non_terminal_count == 0
       - unknown_status_count == 0
    4. Any missing ordinal, pending window, unknown window status, or unknown run status:
       Returns "INCOMPLETE" (fail-closed).
    """
    normalized_run_status = run_status.strip().upper()

    # Rule 1: Authoritative PARTIAL run is never promoted
    if normalized_run_status == "PARTIAL":
        return "PARTIAL"

    # Must have a known terminal run status and valid total windows
    if normalized_run_status not in TERMINAL_RUN_STATUSES or total_w <= 0:
        return "INCOMPLETE"

    # All ordinals 0..total_w-1 must be exhaustively present
    expected_ordinals = set(range(total_w))
    if seen_ordinals != expected_ordinals:
        return "INCOMPLETE"

    # Any non-terminal or unknown window prevents completion
    if non_terminal_count > 0 or unknown_status_count > 0:
        return "INCOMPLETE"

    # Terminal complete check
    if exam_w == total_w and gap_count == 0:
        return "COMPLETE"

    if exam_w > 0 and gap_count > 0 and (exam_w + gap_count == total_w):
        return "COMPLETE_WITH_GAPS"

    return "INCOMPLETE"


def _parse_windows_for_run(
    window_rows: Sequence[Any], total_w: int, run_status: str
) -> tuple[str, int, int, list[JourneyGapRow], list[JourneyReferenceRow]]:
    exam_w = 0
    gap_count = 0
    non_terminal_count = 0
    unknown_status_count = 0
    seen_ordinals: set[int] = set()
    gaps: list[JourneyGapRow] = []
    references: list[JourneyReferenceRow] = []

    for w in window_rows:
        ord_val = _validated_window_ordinal(w.get("ordinal"), total_w)
        if ord_val is not None:
            seen_ordinals.add(ord_val)

        w_status = str(w.get("status") or "").strip().upper()
        if w_status == "EXAMINED":
            exam_w += 1
        elif w_status in TERMINAL_GAP_STATUSES:
            gap_count += 1
            gaps.append(
                JourneyGapRow(
                    ordinal=ord_val,
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
        elif w_status in NON_TERMINAL_WINDOW_STATUSES:
            non_terminal_count += 1
        else:
            unknown_status_count += 1

        unres = w.get("unresolved_refs")
        if isinstance(unres, Sequence) and not isinstance(unres, str | bytes):
            for ref in unres:
                references.append(
                    JourneyReferenceRow(
                        source_identifier=f"Window {ord_val if ord_val is not None else 'Unknown'}",
                        target_reference=str(ref),
                        status="UNRESOLVED",
                        details="Unresolved reference recorded during extraction",
                    )
                )

    cov_status = _derive_window_run_coverage_status(
        total_w=total_w,
        seen_ordinals=seen_ordinals,
        exam_w=exam_w,
        gap_count=gap_count,
        non_terminal_count=non_terminal_count,
        unknown_status_count=unknown_status_count,
        run_status=run_status,
    )
    return cov_status, exam_w, gap_count, gaps, references


def _extract_page_span(action_item: dict[str, Any]) -> str | int | None:
    p_start = action_item.get("page_start")
    p_end = action_item.get("page_end")
    if p_start is not None and p_end is not None and p_start != p_end:
        return f"pp. {p_start}–{p_end}"
    if p_start is not None:
        return f"p. {p_start}"
    return action_item.get("page") or action_item.get("page_number")


def _parse_review_item_references(item_data: dict[str, Any], references_collector: list[JourneyReferenceRow]) -> None:
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


def _build_finding_row(
    r: Any,
    decisions_by_finding: dict[str, dict[str, Any]],
    references_collector: list[JourneyReferenceRow],
) -> JourneyFindingRow | None:
    item_data = r.get("item_data") or {}
    if not isinstance(item_data, dict):
        return None

    _parse_review_item_references(item_data, references_collector)

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
    page = _extract_page_span(action_item)
    clause = action_item.get("clause") or action_item.get("clause_ref")
    dimension = action_item.get("dimension") or action_item.get("category")
    severity = action_item.get("severity") or action_item.get("severity_proposed") or action_item.get("impact_level")

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

    return JourneyFindingRow(
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
        sub_scores: dict[str, float | None] = dict.fromkeys(CANONICAL_DIMENSIONS, None)
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
                global_score, score_reason = _extract_coherence_result(coh_row, sub_scores)
                return global_score, score_reason, sub_scores, "AVAILABLE"

            an_row = (await self._session.execute(text("""
                SELECT coherence_score, coherence_breakdown
                  FROM public.analyses
                 WHERE project_id = CAST(:project_id AS uuid)
                   AND tenant_id = CAST(:tenant_id AS uuid)
                   AND status = 'COMPLETED'
                 ORDER BY completed_at DESC NULLS LAST, created_at DESC
                 LIMIT 1
            """), {"project_id": str(project_id), "tenant_id": str(tenant_id)})).mappings().one_or_none()

            if an_row is not None:
                global_score = _extract_analysis_fallback(an_row, sub_scores)
                return global_score, None, sub_scores, "AVAILABLE"

            # Both SQL sources were queried: no result is absence, not failure.
            return None, None, sub_scores, "UNAVAILABLE"
        except Exception:
            logger.exception("journey_export_coherence_read_failed", project_id=str(project_id))
            return None, None, sub_scores, "ERROR"

    async def _fetch_pinned_revision_meta(self, project_id: UUID, tenant_id: UUID) -> tuple[str | None, dict[str, Any]]:
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
        return pinned_run_id, meta

    async def _load_n4_coverage_and_gaps(
        self, project_id: UUID, tenant_id: UUID
    ) -> tuple[str, int, int, int, list[JourneyGapRow], list[JourneyReferenceRow], str]:
        try:
            pinned_run_id, meta = await self._fetch_pinned_revision_meta(project_id, tenant_id)

            parsed = _parse_metadata_coverage(meta)
            if parsed is not None:
                cov_status, total_w, exam_w, gap_count, gaps = parsed
                return cov_status, total_w, exam_w, gap_count, gaps, [], "AVAILABLE"

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
            if run_row is None:
                # Absence established by a tenant-scoped SQL query, not inferred from empty workbook.
                return "INCOMPLETE", 0, 0, 0, [], [], "UNAVAILABLE"

            active_run_id = run_row["run_id"]
            run_status = str(run_row.get("status") or "")
            total_w = int(run_row.get("total_windows") or 0)

            window_rows = (await self._session.execute(text("""
                SELECT ordinal, status, blocked_reason, unresolved_refs
                  FROM public.n4_extraction_windows
                 WHERE run_id = CAST(:run_id AS uuid)
                   AND tenant_id = CAST(:tenant_id AS uuid)
                 ORDER BY ordinal
            """), {"run_id": str(active_run_id), "tenant_id": str(tenant_id)})).mappings().all()

            cov_status, exam_w, gap_count, gaps, refs = _parse_windows_for_run(window_rows, total_w, run_status)
            return cov_status, total_w, exam_w, gap_count, gaps, refs, "AVAILABLE"
        except Exception:
            logger.exception("journey_export_n4_read_failed", project_id=str(project_id))
            return "INCOMPLETE", 0, 0, 0, [], [], "ERROR"

    async def _fetch_review_items_paginated(
        self, project_id: UUID, tenant_id: UUID
    ) -> list[Any]:
        all_rows: list[Any] = []
        offset = 0
        while offset < REVIEW_ITEMS_MAX_EXPORT:
            batch = (await self._session.execute(text("""
                SELECT id, current_status, approved_by, approved_at, item_data
                  FROM public.review_items
                 WHERE project_id = CAST(:project_id AS uuid)
                   AND tenant_id = CAST(:tenant_id AS uuid)
                 ORDER BY created_at ASC, id ASC
                 LIMIT :limit OFFSET :offset
            """), {
                "project_id": str(project_id),
                "tenant_id": str(tenant_id),
                "limit": REVIEW_ITEMS_BATCH_SIZE,
                "offset": offset,
            })).mappings().all()

            if not batch:
                break
            all_rows.extend(batch)
            if len(batch) < REVIEW_ITEMS_BATCH_SIZE:
                break
            offset += len(batch)
        return all_rows

    async def _load_findings_and_decisions(
        self, project_id: UUID, tenant_id: UUID, references_collector: list[JourneyReferenceRow]
    ) -> tuple[list[JourneyFindingRow], int, int, str]:
        findings: list[JourneyFindingRow] = []
        try:
            count_row = (await self._session.execute(text("""
                SELECT COUNT(*) AS total_count
                  FROM public.review_items
                 WHERE project_id = CAST(:project_id AS uuid)
                   AND tenant_id = CAST(:tenant_id AS uuid)
            """), {"project_id": str(project_id), "tenant_id": str(tenant_id)})).mappings().one_or_none()
            total_items = int(count_row["total_count"]) if count_row and count_row.get("total_count") is not None else 0

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

            review_rows = await self._fetch_review_items_paginated(project_id, tenant_id)

            for r in review_rows:
                row_obj = _build_finding_row(r, decisions_by_finding, references_collector)
                if row_obj is not None:
                    findings.append(row_obj)

            exported_count = len(findings)
            if total_items == 0:
                total_items = exported_count
            return findings, total_items, exported_count, "AVAILABLE"
        except Exception:
            logger.exception("journey_export_findings_read_failed", project_id=str(project_id))
            return [], 0, 0, "ERROR"

    async def load_journey_data(self, project_id: UUID, tenant_id: UUID) -> JourneyExportData:
        proj_name, proj_code, proj_status = await self._load_project_identity(project_id, tenant_id)
        global_score, score_reason, sub_scores, coh_status = await self._load_coherence_scores(project_id, tenant_id)
        cov_status, total_w, exam_w, gap_w, gaps, references, cov_status_src = await self._load_n4_coverage_and_gaps(project_id, tenant_id)
        findings, total_items, exported_count, findings_status = await self._load_findings_and_decisions(project_id, tenant_id, references)

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
            coverage_source_status=cov_status_src,
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
    "_derive_window_run_coverage_status",
]
