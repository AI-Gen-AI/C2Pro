"""TS-UD-PROC-DECIMAL-001: procurement numeric precision contract tests."""

from __future__ import annotations

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
