"""TS-UD-PROC-DECIMAL-001 / TS-UD-PROC-BOM-IDEM-001: procurement schema contracts."""

from __future__ import annotations

from pathlib import Path

from src.procurement.adapters.persistence.models import (
    BOMItemORM,
    BudgetItemORM,
    WBSItemORM,
)


def _assert_numeric_precision(
    model: type,
    column_name: str,
    *,
    precision: int,
    scale: int,
) -> None:
    column_type = model.__table__.c[column_name].type

    assert column_type.precision == precision
    assert column_type.scale == scale


def test_procurement_money_columns_use_wide_decimal_precision() -> None:
    """TS-UD-PROC-DECIMAL-001: money columns support large imported budgets."""
    for model, column_name in (
        (BudgetItemORM, "amount"),
        (WBSItemORM, "budget_allocated"),
        (WBSItemORM, "budget_spent"),
        (BOMItemORM, "unit_price"),
        (BOMItemORM, "total_price"),
    ):
        _assert_numeric_precision(model, column_name, precision=18, scale=2)


def test_bom_quantity_uses_four_decimal_places() -> None:
    """TS-UD-PROC-DECIMAL-001: BOM quantities preserve sub-unit precision."""
    _assert_numeric_precision(BOMItemORM, "quantity", precision=18, scale=4)


def test_bom_items_have_nullable_source_document_linkage() -> None:
    """TS-UD-PROC-BOM-IDEM-001: parsed BOM rows can be replaced per source document."""
    column = BOMItemORM.__table__.c["source_document_id"]

    assert column.nullable is True
    assert any(fk.column.table.name == "documents" for fk in column.foreign_keys)


def test_bom_source_document_migration_reasserts_rls_policy() -> None:
    """TS-UD-PROC-BOM-IDEM-001: migration preserves procurement_bom_items RLS."""
    migration_path = (
        Path(__file__).parents[3]
        / "alembic"
        / "versions"
        / "20260628_0001_add_bom_source_document_id.py"
    )
    migration = migration_path.read_text(encoding="utf-8")

    assert "source_document_id" in migration
    assert "idx_procurement_bom_project_source_document" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "tenant_isolation_procurement_bom_items" in migration
