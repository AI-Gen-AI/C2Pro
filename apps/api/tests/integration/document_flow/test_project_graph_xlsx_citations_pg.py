"""Real PostgreSQL + real XLSX parser + immutable cited ProjectGraph source observations.

No model calls, no synthetic trusted artifact promotion: source authority still
comes from the existing current-revision and RLS SQL seam.
"""
from __future__ import annotations

import importlib.util
import json
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import openpyxl
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from src.analysis.adapters.graph.structured_source_comparison import compare_original_source_rows
from src.analysis.adapters.persistence.document_artifact_repository import SqlAlchemyDocumentArtifactRepository
from src.reporting.adapters.sources.sqlalchemy_current_state_sources import SqlAlchemyCurrentStateSources
from src.reporting.application.current_state_projection import project_source_discrepancies
from src.reporting.application.ports import SourceOk
from src.reporting.domain.current_state_report import SectionStatus
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
        "8.2 La fecha de finalización de las obras será el 30 de junio de 2027. "
        "Es la fecha contractual de entrega definitiva de este proyecto EPC."
    )
    price_text = (
        "4.1 El precio del contrato asciende a 1.000.000 euros y se pagará "
        "por hitos según las condiciones particulares del contrato."
    )
    technical_text = (
        "6.3 Las pruebas de aceptación en fábrica deberán finalizar a más tardar "
        "el 10 de junio de 2027 conforme a la especificación técnica."
    )
    contract_doc, contract_rev = await _upload_and_ingest(
        db, worker, test_user, project_id, filename="contract.docx",
        content=_docx([contract_text, price_text]), document_type=DocumentType.CONTRACT,
    )
    technical_doc, technical_rev = await _upload_and_ingest(
        db, worker, test_user, project_id, filename="specification.docx",
        content=_docx([technical_text]), document_type=DocumentType.TECHNICAL_SPEC,
    )
    schedule_doc, schedule_rev = await _upload_and_ingest(
        db, worker, test_user, project_id, filename="schedule.xlsx",
        content=_xlsx([
            ["Foundations", "2027-01-04", "2027-03-31"],
            ["Pruebas de aceptación en fábrica", "2027-05-01", "2027-07-01"],
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
        ),
        DocumentArtifact(
            document_id=str(technical_doc.id),
            document_revision_id=str(technical_rev.revision_id),
            doc_type="technical_spec",
            extracted_risks=[RiskItem(
                title="Factory acceptance deadline",
                description="Original technical specification milestone",
                source_quote=technical_text,
                source_quote_status="VERIFIED",
                clause_ref="6.3",
            )],
        ),
    ]
    result = compare_original_source_rows(artifacts, rows)
    assert result["source_rows_verified"] >= 4
    assert {x["rule_id"] for x in result["findings"]} == {
        "DET-CRS-SCHDEAD", "DET-CRS-NEGMARGIN", "SPEC-MILESTONE-VS-SCHEDULE",
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
    assert len(stored["findings"]) == 3
    assert all(len(item["sources"]) == 2 for item in stored["findings"])

    # The report reader must never accept a contract/spec quote until its exact
    # immutable revision is trusted. XLSX source rows remain source observations.
    artifact_repository = SqlAlchemyDocumentArtifactRepository(db)
    for artifact in artifacts:
        await artifact_repository.save(
            artifact, project_id=project_id, tenant_id=test_user.tenant_id,
        )
    await db.commit()

    @asynccontextmanager
    async def current_scope(requested_tenant):
        assert requested_tenant == test_user.tenant_id
        yield db

    reader = SqlAlchemyCurrentStateSources(
        current_user=test_user, session_scope=current_scope,
    )
    report_data = await reader.load_source_discrepancies(project_id, test_user.tenant_id)
    section = project_source_discrepancies(SourceOk(report_data))
    assert section.status is SectionStatus.AVAILABLE
    assert section.source_ref == str(report_data["event_id"])
    assert section.data is not None
    assert len(section.data.items) == 3
    assert all(len(item.sources) == 2 and item.scored is False for item in section.data.items)
    assert all(
        item.sources[1].source_locator and item.sources[1].blob_sha256
        for item in section.data.items
    )

    # Stale evidence from another revision must NOT remain visible as current.
    event_id = report_data["event_id"]
    stored = (await db.execute(
        text("SELECT payload FROM project_events WHERE event_id=CAST(:event_id AS uuid)"),
        {"event_id": event_id},
    )).scalar_one()
    stored["findings"][0]["sources"][1]["revision_id"] = str(uuid4())
    await db.execute(
        text("UPDATE project_events SET payload=CAST(:payload AS jsonb) WHERE event_id=CAST(:event_id AS uuid)"),
        {"payload": json.dumps(stored), "event_id": event_id},
    )
    await db.commit()
    refreshed = await reader.load_source_discrepancies(project_id, test_user.tenant_id)
    assert len(refreshed["items"]) == 2, "Stale XLSX revision must be excluded"
