"""PC-3 follow-up: real spreadsheet rows become revision-bound evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import UUID

import openpyxl
import pytest

from src.analysis.application.extract_budget_revision_evidence_use_case import (
    ExtractBudgetRevisionEvidenceUseCase,
)
from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser
from src.documents.domain.models import Document, DocumentStatus, DocumentType
from src.temporal.domain.document_revision import DocumentRevision

TENANT = UUID("11111111-1111-1111-1111-111111111111")
PROJECT = UUID("22222222-2222-2222-2222-222222222222")
DOCUMENT = UUID("33333333-3333-3333-3333-333333333333")
REVISION = UUID("44444444-4444-4444-4444-444444444444")
BASELINE = UUID("55555555-5555-5555-5555-555555555555")
WBS_NODE = UUID("66666666-6666-6666-6666-666666666666")
NOW = datetime(2026, 10, 17, tzinfo=UTC)


def _budget_xlsx(path: Path) -> None:
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = "Budget 2026"
    worksheet.append(
        ["Item", "Quantity", "Unit", "Unit Price", "Total", "Currency", "Tax Basis", "WBS Node ID"]
    )
    worksheet.append(["Concrete", 12, "m3", 100, 1200, "EUR", "NET", str(WBS_NODE)])
    workbook.save(path)


def _document() -> Document:
    return Document(
        id=DOCUMENT,
        tenant_id=TENANT,
        project_id=PROJECT,
        filename="budget.xlsx",
        document_type=DocumentType.BUDGET,
        upload_status=DocumentStatus.PARSED,
        file_format=".xlsx",
    )


def _revision(source: Path | None = None) -> DocumentRevision:
    return DocumentRevision(
        revision_id=REVISION,
        document_id=DOCUMENT,
        project_id=PROJECT,
        tenant_id=TENANT,
        rev_no=1,
        blob_hash=sha256(source.read_bytes()).hexdigest() if source else "a" * 64,
        blob_key="revisions/budget.xlsx",
        valid_from=NOW,
        created_at=NOW,
    )


class _ApprovedScopeService:
    async def require(self, *, tenant_id: UUID, project_id: UUID, node_ids: set[UUID]):
        assert tenant_id == TENANT
        assert project_id == PROJECT
        assert node_ids == {WBS_NODE}
        return BASELINE


@pytest.mark.asyncio
async def test_extracts_a_real_xlsx_row_with_locator_provenance_and_approved_wbs(
    tmp_path: Path,
) -> None:
    """Removing immutable source, numeric, or WBS checks makes this row unsafe."""
    source = tmp_path / "budget.xlsx"
    _budget_xlsx(source)

    result = await ExtractBudgetRevisionEvidenceUseCase(
        parser=ExcelFileParser(), approved_scope_service=_ApprovedScopeService()
    ).execute(
        document=_document(),
        revision=_revision(source),
        source_path=source,
        existing_row_identities=frozenset(),
    )

    [row] = result.rows
    assert row.source_locator == "Budget 2026!2"
    assert row.quantity == 12
    assert row.unit_price == 100
    assert row.amount == 1200
    assert row.numeric_provenance == (("quantity", "12"), ("unit price", "100"), ("total", "1200"))
    assert row.currency == "EUR"
    assert row.tax_basis == "NET"
    assert row.wbs_baseline_id == BASELINE
    assert row.wbs_node_id == WBS_NODE
    assert result.assessment_reason == "approved_budget_comparison_missing"


@pytest.mark.asyncio
async def test_rejects_tampered_xlsx_before_parsing(tmp_path: Path) -> None:
    source = tmp_path / "budget.xlsx"
    _budget_xlsx(source)
    revision = _revision(source)
    source.write_bytes(source.read_bytes() + b"tampered")
    with pytest.raises(Exception, match="blob hash mismatch"):
        await ExtractBudgetRevisionEvidenceUseCase(parser=ExcelFileParser(), approved_scope_service=_ApprovedScopeService()).execute(document=_document(), revision=revision, source_path=source, existing_row_identities=frozenset())


@pytest.mark.asyncio
async def test_real_rows_with_mixed_units_or_monetary_bases_stay_not_assessed(
    tmp_path: Path,
) -> None:
    """Parser output must never become a green result when row semantics conflict."""
    source = tmp_path / "mixed-budget.xlsx"
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.append(["Item", "Quantity", "Unit", "Unit Price", "Total", "Currency", "Tax Basis"])
    worksheet.append(["Concrete", 12, "m3", 100, 1200, "EUR", "NET"])
    worksheet.append(["Rebar", 10, "kg", 90, 900, "USD", "GROSS"])
    workbook.save(source)

    result = await ExtractBudgetRevisionEvidenceUseCase(
        parser=ExcelFileParser(), approved_scope_service=_ApprovedScopeService()
    ).execute(
        document=_document(),
        revision=_revision(source),
        source_path=source,
        existing_row_identities=frozenset(),
    )

    assert len(result.rows) == 2
    assert result.assessment_reason == "incompatible_budget_row_semantics"


@pytest.mark.asyncio
async def test_redelivery_skips_an_already_recorded_revision_locator(tmp_path: Path) -> None:
    """The same immutable revision may be delivered again without duplicate evidence."""
    source = tmp_path / "budget.xlsx"
    _budget_xlsx(source)

    result = await ExtractBudgetRevisionEvidenceUseCase(
        parser=ExcelFileParser(), approved_scope_service=_ApprovedScopeService()
    ).execute(
        document=_document(),
        revision=_revision(source),
        source_path=source,
        existing_row_identities=frozenset({(REVISION, "Budget 2026!2")}),
    )

    assert result.rows == ()
    assert result.assessment_reason == "no_verified_budget_rows"
