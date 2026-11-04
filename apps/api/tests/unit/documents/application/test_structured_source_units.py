"""Source XLSX observations are revision-scoped, atomic, and never WBS/BOM."""

import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.documents.adapters.parsers.excel_file_parser import BudgetRows, ExcelParsingError
from src.documents.application.structured_source_units import (
    _prepare_units,
    load_canonical_source_units,
    stage_structured_source_units,
)


def _scope(path: Path) -> dict:
    return {
        "session": AsyncMock(),
        "parser": AsyncMock(),
        "file_path": path,
        "tenant_id": uuid4(),
        "project_id": uuid4(),
        "document_id": uuid4(),
        "revision_id": uuid4(),
        "blob_hash": "sha256:synthetic-fixture",
        "parser_coverage": {"status": "COMPLETE"},
    }


@pytest.mark.asyncio
async def test_budget_persists_line_and_declared_total_as_source_units(tmp_path):
    scope = _scope(tmp_path / "budget.xlsx")
    rows = BudgetRows([
        {
            "item": "Cables",
            "quantity": Decimal("2.500"),
            "unit_price": Decimal("13.120"),
            "total": Decimal("32.80000"),
            "currency": "EUR",
            "source_locator": "Budget!2",
        }
    ])
    rows.declared_total_rows = [
        {
            "kind": "declared_total",
            "item": "TOTAL",
            "total": Decimal("32.80000"),
            "source_locator": "Budget!3",
        }
    ]
    scope["parser"].parse_budget.return_value = rows
    result = await stage_structured_source_units(**scope, family="budget")

    assert result["state"] == "SOURCE_OBSERVED"
    assert result["units"] == 2
    assert result["parser_coverage"] == "COMPLETE"
    scope["parser"].parse_budget.assert_awaited_once_with(
        scope["file_path"], include_evidence=True
    )
    assert scope["session"].execute.await_count == 2
    sql_parameters = scope["session"].execute.await_args.args[1]
    assert len(sql_parameters) == 2
    assert {p["source_locator"] for p in sql_parameters} == {"Budget!2", "Budget!3"}
    line = next(p for p in sql_parameters if p["source_locator"] == "Budget!2")
    payload = json.loads(line["payload"])
    assert payload["quantity"] == "2.500"
    assert payload["unit_price"] == "13.120"
    assert payload["kind"] == "line_item"
    assert line["revision_id"] == str(scope["revision_id"])
    assert all("source_locator" in json.loads(p["payload"]) for p in sql_parameters)


@pytest.mark.asyncio
async def test_schedule_preserves_dependency_and_original_row(tmp_path):
    scope = _scope(tmp_path / "schedule.xlsx")
    scope["parser"].parse_schedule.return_value = [
        {
            "task": "Factory acceptance",
            "predecessors": "SCH-01 FS+2d",
            "source_activity_id": "SCH-02",
            "source_locator": "Schedule!6",
        }
    ]
    result = await stage_structured_source_units(**scope, family="schedule")
    assert result["units"] == 1
    payload = json.loads(scope["session"].execute.await_args.args[1][0]["payload"])
    assert payload["kind"] == "activity"
    assert payload["predecessors"] == "SCH-01 FS+2d"
    assert payload["source_activity_id"] == "SCH-02"


@pytest.mark.asyncio
async def test_formulas_fail_closed_for_source_units_but_not_ingestion(tmp_path):
    scope = _scope(tmp_path / "budget.xlsx")
    scope["parser"].parse_budget.side_effect = ExcelParsingError(
        "Unverified formula-derived budget evidence at Budget!4"
    )
    result = await stage_structured_source_units(**scope, family="budget")
    assert result == {
        "state": "UNASSESSED",
        "reason": "unverified_formula_or_source_cell",
        "units": 0,
    }
    # Revision's prior records are cleared; no new unverified rows are written.
    scope["session"].execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_bc3_and_revisionless_sources_do_not_write_untraceable_rows(tmp_path):
    for reason, name, revision_id in (
        ("verified_source_format_unsupported", "budget.bc3", uuid4()),
        ("immutable_source_revision_missing", "budget.xlsx", None),
    ):
        scope = _scope(tmp_path / name)
        scope["revision_id"] = revision_id
        result = await stage_structured_source_units(**scope, family="budget")
        assert result["reason"] == reason
        scope["session"].execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_partial_workbook_is_not_marked_complete(tmp_path):
    scope = _scope(tmp_path / "schedule.xlsx")
    scope["parser_coverage"] = {"status": "PARTIAL", "unprocessed_worksheets": ["Annex"]}
    scope["parser"].parse_schedule.return_value = [
        {"task": "Procurement", "source_locator": "Plan!2"}
    ]
    result = await stage_structured_source_units(**scope, family="schedule")
    assert result["state"] == "SOURCE_OBSERVED"
    assert result["parser_coverage"] == "PARTIAL"
    assert result["source_scope"] == "active_worksheet_only"


def test_duplicate_or_missing_locator_is_never_silently_deduplicated():
    with pytest.raises(ValueError, match="SOURCE_UNIT_LOCATOR_DUPLICATED"):
        _prepare_units([
            {"task": "One", "source_locator": "Plan!2"},
            {"task": "Two", "source_locator": "Plan!2"},
        ], family="schedule")
    with pytest.raises(ValueError, match="SOURCE_UNIT_LOCATOR_MISSING"):
        _prepare_units([{"task": "No source"}], family="schedule")



@pytest.mark.asyncio
async def test_r2_temporary_filename_does_not_hide_verified_xlsx_format(tmp_path):
    scope = _scope(tmp_path / "revision_object_without_suffix")
    scope["parser"].parse_schedule.return_value = [
        {"task": "Handover", "source_locator": "Plan!12"}
    ]
    result = await stage_structured_source_units(
        **scope, family="schedule", source_format=".xlsx"
    )
    assert result["units"] == 1


@pytest.mark.asyncio
async def test_reader_queries_canonical_revision_not_pending_proposal():
    session = AsyncMock()
    result = MagicMock()
    result.mappings.return_value.all.return_value = [{
        "family": "schedule",
        "source_locator": "Plan!4",
        "payload": {"task": "Milestone"},
    }]
    session.execute.return_value = result
    records = await load_canonical_source_units(
        session=session,
        tenant_id=uuid4(),
        project_id=uuid4(),
        family="schedule",
    )
    assert len(records) == 1
    assert records[0]["source_locator"] == "Plan!4"
    query = str(session.execute.await_args.args[0])
    assert "cur.canonical" in query
    assert "cur.revision_id = u.revision_id" in query
    assert "u.tenant_id = CAST(:tenant_id AS uuid)" in query
    assert "u.project_id = CAST(:project_id AS uuid)" in query


@pytest.mark.asyncio
async def test_reader_rejects_other_document_families():
    session = AsyncMock()
    with pytest.raises(ValueError, match="SOURCE_UNIT_FAMILY_INVALID"):
        await load_canonical_source_units(
            session=session, tenant_id=uuid4(), project_id=uuid4(),
            family="contract",
        )
    session.execute.assert_not_awaited()
