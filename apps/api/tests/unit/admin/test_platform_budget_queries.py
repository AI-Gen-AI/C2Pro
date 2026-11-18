"""Focused budget list query tests with synthetic rows only, never UAT DB."""
from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy.sql.elements import TextClause

from src.admin.adapters.http.platform_budget_router import list_platform_budgets
from src.core.auth.platform_operator import PlatformOperator


def _row(tenant_id: str, name: str, spent: str = "0", reserved: str = "0") -> dict[str, Any]:
    return {
        "tenant_id": tenant_id, "name": name, "slug": name.lower().replace(" ", "-"),
        "is_active": True, "updated_at": None,
        "owner_cap": Decimal("5"), "bucket_cap": Decimal("5"),
        "tenant_spent": Decimal(spent), "bucket_spent": Decimal(spent),
        "tenant_reserved": Decimal(reserved), "bucket_reserved": Decimal(reserved),
    }


class QueryResult:
    def __init__(self, data: Any) -> None:
        self.data = data

    def scalar_one(self) -> Any:
        return self.data

    def mappings(self) -> QueryResult:
        return self

    def all(self) -> Any:
        return self.data


class FakeConnection:
    def __init__(self, items: list[dict[str, Any]]) -> None:
        self.items = items
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def execute(self, stmt: TextClause, params: dict[str, Any]) -> QueryResult:
        sql = stmt.text
        self.calls.append((sql, dict(params)))
        assert params["limit"] <= 100
        assert params["offset"] >= 0
        assert "public.tenants" in sql
        assert "documents" not in sql
        assert "tenant_id = :" not in sql
        assert "slug ILIKE :search" in sql, "Search must support tenant name and slug"
        name = params["search"].strip("%").lower()
        filtered = [
            row for row in self.items
            if name in row["name"].lower() or name in row["slug"].lower()
        ]
        if "count(*)" in sql:
            return QueryResult(len(filtered))
        return QueryResult(filtered[params["offset"]: params["offset"] + params["limit"]])


def _operator() -> PlatformOperator:
    return PlatformOperator(
        clerk_user_id="user_authorized", clerk_org_id="org_operator", email=None
    )


@pytest.mark.asyncio
async def test_tenant_pagination_search_and_totals_with_synthetic_data() -> None:
    connection = FakeConnection([
        _row("tenant-1", "Alpha EPC", "1", "0.5"),
        _row("tenant-2", "Beta Industrial", "2", "1"),
        _row("tenant-3", "Beta Labs", "0", "0"),
    ])
    @asynccontextmanager
    async def fake_read():
        yield connection
    with patch(
        "src.admin.adapters.http.platform_budget_router._budget_read_connection",
        fake_read,
    ):
        first = await list_platform_budgets(
            query="beta", limit=1, offset=0, operator=_operator()
        )
        second = await list_platform_budgets(
            query="beta", limit=1, offset=1, operator=_operator()
        )
    assert first.total == second.total == 2
    assert first.items[0].tenant_id == "tenant-2"
    assert second.items[0].tenant_id == "tenant-3"
    assert first.items[0].available_usd == Decimal("2")
    assert len(connection.calls) == 4
    assert all(params["search"] == "%beta%" for _, params in connection.calls)


@pytest.mark.asyncio
async def test_empty_result_and_escaped_search_params() -> None:
    connection = FakeConnection([_row("tenant-1", "Alpha")])
    @asynccontextmanager
    async def fake_read():
        yield connection
    with patch(
        "src.admin.adapters.http.platform_budget_router._budget_read_connection",
        fake_read,
    ):
        empty = await list_platform_budgets(
            query="no-such-tenant", limit=25, offset=0, operator=_operator()
        )
    assert empty.total == 0 and empty.items == []
    assert empty.limit == 25 and empty.offset == 0


def test_missing_and_divergent_buckets_are_disclosed_not_marked_reconciled() -> None:
    from src.admin.adapters.http.platform_budget_router import _item
    row = _row("tenant-1", "Alpha", "1", "0.25")
    row["bucket_cap"] = None
    assert _item(row).budget_status == "NO_TENANT_BUCKET"
    row["bucket_cap"] = Decimal("2")
    row["bucket_spent"] = Decimal("2")
    assert _item(row).budget_status == "COUNTERS_DIVERGED"
    assert _item(row).available_usd == Decimal("0")


def test_timestamp_is_typed_or_unset() -> None:
    from datetime import UTC, datetime
    from src.admin.adapters.http.platform_budget_router import _item
    row = _row("tenant-1", "Alpha")
    row["updated_at"] = "bad-timestamp"
    assert _item(row).last_tenant_update is None
    now = datetime.now(UTC)
    row["updated_at"] = now
    assert _item(row).last_tenant_update == now
