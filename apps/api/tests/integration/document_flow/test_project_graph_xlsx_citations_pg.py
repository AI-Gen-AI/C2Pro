"""Real PostgreSQL + real XLSX parser + immutable cited ProjectGraph source observations.

No model calls, no synthetic trusted artifact promotion: source authority still
comes from the existing current-revision and RLS SQL seam.
"""
from __future__ import annotations

import importlib.util
from io import BytesIO
from pathlib import Path

import openpyxl
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from src.analysis.adapters.graph.structured_source_comparison import compare_original_source_rows
from src.analysis.domain.contracts import DocumentArtifact, RiskItem
from src.core.tasks.project_graph_tasks import persist_provisional_source_discrepancies
from src.documents.application.structured_source_units import load_canonical_source_units
from src.documents.domain.models import DocumentType
from tests.integration.document_flow.test_contract_schedule_completion_flow import (
    _docx, _project, _upload_and_ingest, _xlsx,
    worker,  # noqa: F401 - reuse isolated genuine ingestion fixture
)

pytestmark = pytest.mark.asyncio


def _budget() -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["Item", "Quantity", "Unit", "Unit Price", "Total", "Currency"])
    sheet.append(["Transformador EPC", 1, "ud", 600000, 600000, "EUR"])
    sheet.append(["Total presupuesto", None, None, None, 1300000, "EUR"])
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


async def _ensure_real_source_unit_migration(db):
    exists = await db.scalar(text("SELECT to_regclass('public.document_source_units')"))
    if exists:
        return
    location = Path(__file__).resolve().parents[3] / "alembic" / "versions" / "20261104_0001_document_source_units.py"
    spec = importlib.util.spec_from_file_location("source_unit_pg_test", location)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def upgrade(sync_connection):
        original = module.op
        module.op = Operations(MigrationContext.configure(sync_connection))
        try:
            module.upgrade()
        finally:
            module.op = original

    connection = await db.connection()
    await connection.run_sync(upgrade)
    await db.commit()


async def test_real_pg_xlsx_rows_compare_to_verified_contract_and_save_provisional_event(
    db, worker, test_user,
):
    await _ensure_real_source_unit_migration(db)
    project_id = await _project(db, test_user.tenant_id)
    contract_text = (
        "La fecha de finalización de las obras será el 30 de junio de 2027. "
        "Es la fecha contractual de entrega definitiva de este proyecto EPC."
    )
    price_text = (
        "El precio del contrato asciende a 1.000.000 euros y se pagará "
        "por hitos según las condiciones particulares del contrato."
    )
    contract_doc, contract_rev = await _upload_and_ingest(
        db, worker, test_user, project_id, filename="contract.docx",
        content=_docx([contract_text, price_text]), document_type=DocumentType.CONTRACT,
    )
    schedule_doc, schedule_rev = await _upload_and_ingest(
        db, worker, test_user, project_id, filename="schedule.xlsx",
        content=_xlsx([
            ["Foundations", "2027-01-04", "2027-03-31"],
            ["Handover", "2027-08-02", "2027-09-30"],
        ]), document_type=DocumentType.SCHEDULE,
    )
    budget_doc, budget_rev = await _upload_and_ingest(
        db, worker, test_user, project_id, filename="budget.xlsx",
        content=_budget(), document_type=DocumentType.BUDGET,
    )
    await db.commit()
    await db.execute(
        text("SELECT set_config('app.current_tenant', :t, true)"),
        {"t": str(test_user.tenant_id)},
    )
    rows = []
    for family in ("budget", "schedule"):
        rows.extend(await load_canonical_source_units(
            session=db, tenant_id=test_user.tenant_id,
            project_id=project_id, family=family,
        ))
    assert {str(row["document_id"]) for row in rows} == {
        str(schedule_doc.id), str(budget_doc.id)
    }, "Only the canonical revision's source rows must be read"
    assert {str(row["revision_id"]) for row in rows} == {
        str(schedule_rev.revision_id), str(budget_rev.revision_id)
    }
    artifacts = [
        DocumentArtifact(
            document_id=str(contract_doc.id),
            document_revision_id=str(contract_rev.revision_id),
            doc_type="contract",
            extracted_risks=[
                RiskItem(
                    title="Contract delivery", description="Contractual completion",
                    source_quote=contract_text, source_quote_status="VERIFIED", clause_ref="8.2",
                ),
                RiskItem(
                    title="Contract price", description="EPC price",
                    source_quote=price_text, source_quote_status="VERIFIED", clause_ref="4.1",
                ),
            ],
        )
    ]
    result = compare_original_source_rows(artifacts, rows)
    assert result["source_rows_verified"] >= 3
    assert {x["rule_id"] for x in result["findings"]} == {
        "DET-CRS-SCHDEAD", "DET-CRS-NEGMARGIN",
    }, result
    assert await persist_provisional_source_discrepancies(
        db, project_id=project_id, tenant_id=test_user.tenant_id, comparison=result
    )
    await db.commit()
    stored = (await db.execute(
        text(
            "SELECT payload FROM project_events WHERE project_id=:p AND tenant_id=:t "
            "AND event_type='project_graph.source_discrepancies_observed'"
        ),
        {"p": project_id, "t": test_user.tenant_id},
    )).scalar_one()
    assert stored["state"] == "PROVISIONAL"
    assert stored["scoring_policy"] == "not_scored"
    assert len(stored["findings"]) == 2
    assert all(len(item["sources"]) == 2 for item in stored["findings"])
