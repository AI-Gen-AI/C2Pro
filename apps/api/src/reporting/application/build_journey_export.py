"""TS-P0D-REPORT-004 - Build Journey Excel Export (WP JV1-A19).

Generates journey.xlsx with openpyxl:
- Hojas Summary (Score, 6 subscores, cobertura), Findings (título, interpretación
  IA etiquetada, cita exacta, página, cláusula, decisión, revisor, fecha),
  Gaps & References.
- Valores derivados exclusivamente de modelos de lectura (read models).
- Validación de aislamiento multi-tenant y apertura sin advertencias en Excel.
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

import openpyxl
import structlog
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
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
    attempts: int
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


def build_journey_workbook(data: JourneyExportData) -> openpyxl.Workbook:
    """Generate a clean, warning-free openpyxl workbook with 3 required sheets."""
    wb = openpyxl.Workbook()

    # Styling primitives
    font_title = Font(name="Calibri", size=14, bold=True, color="1F4E78")
    font_section = Font(name="Calibri", size=12, bold=True, color="1F4E78")
    font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    font_bold = Font(name="Calibri", size=11, bold=True)
    font_regular = Font(name="Calibri", size=11)
    font_italic = Font(name="Calibri", size=10, italic=True, color="595959")

    fill_header_navy = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    fill_header_dark = PatternFill(start_color="2E4053", end_color="2E4053", fill_type="solid")
    fill_zebra = PatternFill(start_color="F2F4F7", end_color="F2F4F7", fill_type="solid")

    thin_border_side = Side(style="thin", color="D9D9D9")
    thin_border = Border(
        left=thin_border_side,
        right=thin_border_side,
        top=thin_border_side,
        bottom=thin_border_side,
    )

    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")
    align_wrap = Alignment(horizontal="left", vertical="top", wrap_text=True)

    # ──────────────────────────────────────────────────────────────────────────
    # SHEET 1: Summary
    # ──────────────────────────────────────────────────────────────────────────
    ws_summary = wb.active
    ws_summary.title = "Summary"
    ws_summary.views.sheetView[0].showGridLines = True

    # Title Block
    ws_summary.cell(row=1, column=1, value="C2Pro Journey V1 - Project Summary Report").font = font_title

    meta_items = [
        ("Project Name", data.summary.project_name),
        ("Project Code", data.summary.project_code or "N/A"),
        ("Project ID", str(data.summary.project_id)),
        ("Project Status", data.summary.status),
        ("Report Generated At", _format_date(data.summary.generated_at)),
    ]
    curr_row = 3
    for label, meta_val in meta_items:
        c_lbl = ws_summary.cell(row=curr_row, column=1, value=label)
        c_lbl.font = font_bold
        c_val = ws_summary.cell(row=curr_row, column=2, value=meta_val)
        c_val.font = font_regular
        curr_row += 1

    # Section: Scores Overview
    curr_row += 1
    ws_summary.cell(row=curr_row, column=1, value="Coherence Score Overview").font = font_section
    curr_row += 1

    score_headers = ["Metric", "Value", "Description"]
    for col_idx, h in enumerate(score_headers, start=1):
        cell = ws_summary.cell(row=curr_row, column=col_idx, value=h)
        cell.font = font_header
        cell.fill = fill_header_navy
        cell.alignment = align_left
        cell.border = thin_border
    curr_row += 1

    score_rows: list[tuple[str, object, str]] = [
        ("Global Coherence Score", _format_score(data.summary.global_score), "Consolidated project coherence indicator"),
        ("Validated Score", _format_score(data.summary.trusted_score), "Based exclusively on reviewer-confirmed facts"),
        ("Projected Score", _format_score(data.summary.projected_score), "Validated score adjusted for pending AI hypotheses"),
        ("Score Reason / State", data.summary.score_reason or "Assessed without material blockers", "Current evaluation explanation"),
    ]
    for metric, score_val, desc in score_rows:
        c1 = ws_summary.cell(row=curr_row, column=1, value=metric)
        c2 = ws_summary.cell(row=curr_row, column=2, value=score_val)
        c3 = ws_summary.cell(row=curr_row, column=3, value=desc)
        for c in (c1, c2, c3):
            c.font = font_regular
            c.border = thin_border
        curr_row += 1

    # Section: 6 Canonical Subscores
    curr_row += 1
    ws_summary.cell(row=curr_row, column=1, value="Canonical Dimensions (6 Subscores)").font = font_section
    curr_row += 1

    sub_headers = ["Dimension", "Weight", "Score", "Evaluation Status"]
    for col_idx, h in enumerate(sub_headers, start=1):
        cell = ws_summary.cell(row=curr_row, column=col_idx, value=h)
        cell.font = font_header
        cell.fill = fill_header_navy
        cell.alignment = align_left
        cell.border = thin_border
    curr_row += 1

    for dim in CANONICAL_DIMENSIONS:
        weight_pct = f"{int(DIMENSION_WEIGHTS.get(dim, 0.15) * 100)}%"
        sub_val = data.summary.sub_scores.get(dim)
        eval_status = "Assessed" if sub_val is not None else "Not Evaluated"
        c1 = ws_summary.cell(row=curr_row, column=1, value=dim)
        c2 = ws_summary.cell(row=curr_row, column=2, value=weight_pct)
        c3 = ws_summary.cell(row=curr_row, column=3, value=_format_score(sub_val))
        c4 = ws_summary.cell(row=curr_row, column=4, value=eval_status)
        for c in (c1, c2, c3, c4):
            c.font = font_regular
            c.border = thin_border
        curr_row += 1

    # Section: Coverage (Cobertura N4)
    curr_row += 1
    ws_summary.cell(row=curr_row, column=1, value="Contract Analysis Coverage (N4)").font = font_section
    curr_row += 1

    cov_headers = ["Coverage Metric", "Value"]
    for col_idx, h in enumerate(cov_headers, start=1):
        cell = ws_summary.cell(row=curr_row, column=col_idx, value=h)
        cell.font = font_header
        cell.fill = fill_header_navy
        cell.alignment = align_left
        cell.border = thin_border
    curr_row += 1

    total_w = data.summary.total_windows
    exam_w = data.summary.examined_windows
    gap_w = data.summary.gap_windows_count
    cov_pct = f"{round((exam_w / total_w) * 100, 1)}%" if total_w > 0 else "0.0%"

    cov_rows: list[tuple[str, object]] = [
        ("N4 Coverage Status", data.summary.coverage_status or "INCOMPLETE"),
        ("Total Contract Windows", total_w),
        ("Examined Windows", exam_w),
        ("Gap Windows", gap_w),
        ("Examined Window Ratio", cov_pct),
    ]
    for cov_metric, cov_val in cov_rows:
        c1 = ws_summary.cell(row=curr_row, column=1, value=cov_metric)
        c2 = ws_summary.cell(row=curr_row, column=2, value=cov_val)
        for c in (c1, c2):
            c.font = font_regular
            c.border = thin_border
        curr_row += 1

    # ──────────────────────────────────────────────────────────────────────────
    # SHEET 2: Findings
    # ──────────────────────────────────────────────────────────────────────────
    ws_findings = wb.create_sheet(title="Findings")
    ws_findings.views.sheetView[0].showGridLines = True

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
        cell = ws_findings.cell(row=1, column=col_idx, value=h)
        cell.font = font_header
        cell.fill = fill_header_dark
        cell.alignment = align_center
        cell.border = thin_border

    if not data.findings:
        ws_findings.cell(
            row=2, column=1, value="No findings recorded for this project."
        ).font = font_italic
    else:
        for row_idx, f in enumerate(data.findings, start=2):
            # Label AI interpretation clearly
            interpretation = f.ai_interpretation.strip()
            if interpretation and not interpretation.startswith("[IA Proposal]"):
                interpretation = f"[IA Proposal] {interpretation}"

            page_val = str(f.page) if f.page is not None else "Unspecified"

            row_data: list[object] = [
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
            fill = fill_zebra if row_idx % 2 == 1 else None
            for col_idx, finding_val in enumerate(row_data, start=1):
                cell = ws_findings.cell(row=row_idx, column=col_idx, value=finding_val)
                cell.font = font_regular
                cell.border = thin_border
                cell.alignment = align_wrap if col_idx in (1, 2, 3) else align_center
                if fill:
                    cell.fill = fill

    # ──────────────────────────────────────────────────────────────────────────
    # SHEET 3: Gaps & References
    # ──────────────────────────────────────────────────────────────────────────
    ws_gaps = wb.create_sheet(title="Gaps & References")
    ws_gaps.views.sheetView[0].showGridLines = True

    # Part A: Gaps
    ws_gaps.cell(row=1, column=1, value="N4 Contract Coverage Gaps").font = font_section

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
        cell = ws_gaps.cell(row=2, column=col_idx, value=h)
        cell.font = font_header
        cell.fill = fill_header_dark
        cell.alignment = align_center
        cell.border = thin_border

    gap_row_idx = 3
    if not data.gaps:
        ws_gaps.cell(
            row=gap_row_idx,
            column=1,
            value="No coverage gaps recorded (full window coverage or no analysis).",
        ).font = font_italic
        gap_row_idx += 1
    else:
        for g in data.gaps:
            pages = (
                f"pp. {g.page_start}–{g.page_end}"
                if g.page_start is not None and g.page_end is not None
                else (f"p. {g.page_start}" if g.page_start is not None else "Unmapped")
            )
            g_vals: list[object] = [
                g.ordinal,
                g.failure_kind,
                g.reason,
                g.attempts,
                pages,
                g.resolution,
                g.closed_reason or "N/A",
                g.closed_by or "N/A",
                _format_date(g.closed_at),
            ]
            fill = fill_zebra if gap_row_idx % 2 == 1 else None
            for col_idx, gap_val in enumerate(g_vals, start=1):
                cell = ws_gaps.cell(row=gap_row_idx, column=col_idx, value=gap_val)
                cell.font = font_regular
                cell.border = thin_border
                cell.alignment = align_center if col_idx in (1, 2, 4, 5, 6, 8, 9) else align_wrap
                if fill:
                    cell.fill = fill
            gap_row_idx += 1

    # Part B: References / Remisiones
    gap_row_idx += 2
    ws_gaps.cell(row=gap_row_idx, column=1, value="Cross-Document References & Remisiones").font = font_section
    gap_row_idx += 1

    ref_headers = [
        "Source Element / Clause",
        "Target Reference (Remisión)",
        "Resolution Status",
        "Details / Context",
    ]
    for col_idx, h in enumerate(ref_headers, start=1):
        cell = ws_gaps.cell(row=gap_row_idx, column=col_idx, value=h)
        cell.font = font_header
        cell.fill = fill_header_dark
        cell.alignment = align_center
        cell.border = thin_border
    gap_row_idx += 1

    if not data.references:
        ws_gaps.cell(
            row=gap_row_idx,
            column=1,
            value="No unresolved contract references recorded.",
        ).font = font_italic
    else:
        for r in data.references:
            r_vals: list[object] = [
                r.source_identifier,
                r.target_reference,
                r.status,
                r.details or "N/A",
            ]
            fill = fill_zebra if gap_row_idx % 2 == 1 else None
            for col_idx, ref_val in enumerate(r_vals, start=1):
                cell = ws_gaps.cell(row=gap_row_idx, column=col_idx, value=ref_val)
                cell.font = font_regular
                cell.border = thin_border
                cell.alignment = align_center if col_idx == 3 else align_wrap
                if fill:
                    cell.fill = fill
            gap_row_idx += 1

    # Auto-adjust column widths across all sheets
    for ws in (ws_summary, ws_findings, ws_gaps):
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                if cell.value is not None:
                    lines = str(cell.value).split("\n")
                    for line in lines:
                        max_len = max(max_len, len(line))
            # Keep widths within comfortable margins
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 65)

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

    async def load_journey_data(self, project_id: UUID, tenant_id: UUID) -> JourneyExportData:
        session = self._session

        # 1. Project identity
        proj_row = (await session.execute(text("""
            SELECT id, name, code, status
              FROM public.projects
             WHERE id = CAST(:project_id AS uuid)
               AND tenant_id = CAST(:tenant_id AS uuid)
        """), {"project_id": str(project_id), "tenant_id": str(tenant_id)})).mappings().one_or_none()

        proj_name = str(proj_row["name"]) if proj_row and proj_row.get("name") else "Project"
        proj_code = str(proj_row["code"]) if proj_row and proj_row.get("code") else None
        proj_status = str(proj_row["status"]) if proj_row and proj_row.get("status") else "UNKNOWN"

        # 2. Coherence dashboard / scores
        global_score: float | None = None
        trusted_score: float | None = None
        projected_score: float | None = None
        score_reason: str | None = None
        sub_scores: dict[str, float | None] = dict.fromkeys(CANONICAL_DIMENSIONS, None)

        try:
            coh_row = (await session.execute(text("""
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
                    trusted_score = global_score
                score_reason = coh_row.get("score_reason")
                cats = coh_row.get("category_scores")
                if isinstance(cats, dict):
                    for k, v in cats.items():
                        norm_k = str(k).upper()
                        if norm_k in sub_scores:
                            sub_scores[norm_k] = float(v) if v is not None else None
            else:
                # Fallback to latest completed analysis
                an_row = (await session.execute(text("""
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
                    trusted_score = global_score
                    breakdown = an_row.get("coherence_breakdown")
                    if isinstance(breakdown, dict):
                        for k, v in breakdown.items():
                            norm_k = str(k).upper()
                            if norm_k in sub_scores:
                                sub_scores[norm_k] = float(v) if v is not None else None
        except Exception:
            logger.exception("journey_export_coherence_read_failed", project_id=str(project_id))

        # 3. N4 Runs, Windows, Gaps and References
        coverage_status: str = "INCOMPLETE"
        total_windows = 0
        examined_windows = 0
        gap_windows_count = 0
        gaps: list[JourneyGapRow] = []
        references: list[JourneyReferenceRow] = []

        try:
            run_row = (await session.execute(text("""
                SELECT run_id, status, total_windows
                  FROM public.n4_extraction_runs
                 WHERE project_id = CAST(:project_id AS uuid)
                   AND tenant_id = CAST(:tenant_id AS uuid)
                 ORDER BY created_at DESC
                 LIMIT 1
            """), {"project_id": str(project_id), "tenant_id": str(tenant_id)})).mappings().one_or_none()

            if run_row is not None:
                pinned_run_id = run_row["run_id"]
                total_windows = int(run_row.get("total_windows") or 0)

                window_rows = (await session.execute(text("""
                    SELECT ordinal, status, blocked_reason, unresolved_refs
                      FROM public.n4_extraction_windows
                     WHERE run_id = CAST(:run_id AS uuid)
                       AND tenant_id = CAST(:tenant_id AS uuid)
                     ORDER BY ordinal
                """), {"run_id": str(pinned_run_id), "tenant_id": str(tenant_id)})).mappings().all()

                gap_ordinals: list[int] = []
                for w in window_rows:
                    w_status = str(w.get("status") or "")
                    if w_status == "EXAMINED":
                        examined_windows += 1
                    elif w_status in ("BLOCKED", "FAILED"):
                        gap_windows_count += 1
                        gap_ordinals.append(int(w["ordinal"]))
                        gaps.append(
                            JourneyGapRow(
                                ordinal=int(w["ordinal"]),
                                failure_kind=str(w.get("blocked_reason") or "UNKNOWN_BLOCK"),
                                reason=str(w.get("blocked_reason") or "Window could not be examined"),
                                attempts=1,
                                page_start=None,
                                page_end=None,
                                resolution="OPEN",
                                closed_reason=None,
                                closed_by=None,
                                closed_at=None,
                            )
                        )

                    # Collect unresolved refs
                    unres = w.get("unresolved_refs")
                    if isinstance(unres, Sequence) and not isinstance(unres, str | bytes):
                        for ref in unres:
                            references.append(
                                JourneyReferenceRow(
                                    source_identifier=f"Window {w['ordinal']}",
                                    target_reference=str(ref),
                                    status="UNRESOLVED",
                                    details="Remisión not yet resolved across contract sections",
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

        # 4. Findings and Human Decisions
        findings: list[JourneyFindingRow] = []
        try:
            # Load candidate findings or review items
            review_rows = (await session.execute(text("""
                SELECT id, current_status, approved_by, approved_at, item_data
                  FROM public.review_items
                 WHERE project_id = CAST(:project_id AS uuid)
                   AND tenant_id = CAST(:tenant_id AS uuid)
                 ORDER BY created_at
                 LIMIT 200
            """), {"project_id": str(project_id), "tenant_id": str(tenant_id)})).mappings().all()

            for r in review_rows:
                item_data = r.get("item_data") or {}
                if not isinstance(item_data, dict):
                    continue

                # Interoperability with A1/A7 contract: check n4_coverage embedded in item_data
                n4_cov = item_data.get("n4_coverage") or item_data.get("analysis_n4_coverage")
                if isinstance(n4_cov, dict):
                    if n4_cov.get("status"):
                        coverage_status = str(n4_cov["status"])
                    if n4_cov.get("total_windows") is not None:
                        total_windows = int(n4_cov["total_windows"])
                    if n4_cov.get("examined_windows") is not None:
                        examined_windows = int(n4_cov["examined_windows"])
                    if isinstance(n4_cov.get("gap_windows"), Sequence) and not isinstance(n4_cov["gap_windows"], str | bytes):
                        gap_windows_count = len(n4_cov["gap_windows"])
                    if isinstance(n4_cov.get("gaps"), Sequence) and not gaps:
                        for g_dict in n4_cov["gaps"]:
                            if isinstance(g_dict, dict):
                                gaps.append(
                                    JourneyGapRow(
                                        ordinal=int(g_dict.get("ordinal", 0)),
                                        failure_kind=str(g_dict.get("failure_kind") or "UNKNOWN_BLOCK"),
                                        reason=str(g_dict.get("reason") or "Window gap"),
                                        attempts=int(g_dict.get("attempts", 1)),
                                        page_start=g_dict.get("page_start"),
                                        page_end=g_dict.get("page_end"),
                                        resolution=str(g_dict.get("resolution") or "OPEN"),
                                        closed_reason=g_dict.get("closed_reason"),
                                        closed_by=g_dict.get("closed_by"),
                                        closed_at=g_dict.get("closed_at"),
                                    )
                                )

                # Interoperability with A7 remisiones / references embedded in item_data
                ref_items = item_data.get("references") or item_data.get("remisiones") or item_data.get("reference_register")
                if isinstance(ref_items, Sequence) and not isinstance(ref_items, str | bytes):
                    for ref_dict in ref_items:
                        if isinstance(ref_dict, dict):
                            references.append(
                                JourneyReferenceRow(
                                    source_identifier=str(ref_dict.get("source") or ref_dict.get("source_clause") or "Contract Section"),
                                    target_reference=str(ref_dict.get("target") or ref_dict.get("target_reference") or ref_dict.get("reference") or ""),
                                    status=str(ref_dict.get("status") or "UNRESOLVED"),
                                    details=ref_dict.get("details") or ref_dict.get("reason"),
                                )
                            )

                # Could be structured as action_item, risk, candidate finding, or N4SharedFinding
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

                findings.append(
                    JourneyFindingRow(
                        finding_id=str(r["id"]),
                        title=title,
                        ai_interpretation=interpretation,
                        exact_quote=exact_quote,
                        page=page,
                        clause=clause,
                        dimension=str(dimension) if dimension else None,
                        severity=str(severity) if severity else None,
                        decision=str(r.get("current_status") or "PROPOSED"),
                        reviewer=str(r.get("approved_by") or "") if r.get("approved_by") else None,
                        decided_at=r.get("approved_at"),
                    )
                )
        except Exception:
            logger.exception("journey_export_findings_read_failed", project_id=str(project_id))

        summary = JourneySummaryData(
            project_id=project_id,
            project_name=proj_name,
            project_code=proj_code,
            status=proj_status,
            global_score=global_score,
            trusted_score=trusted_score,
            projected_score=projected_score,
            score_reason=score_reason,
            sub_scores=sub_scores,
            coverage_status=coverage_status,
            total_windows=total_windows,
            examined_windows=examined_windows,
            gap_windows_count=gap_windows_count,
            generated_at=datetime.now(UTC),
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
]
