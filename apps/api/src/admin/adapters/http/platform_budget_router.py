"""Read-only platform budget table. No tenant-admin cross-tenant fallback.

Feature deliberately fails closed until a separately approved, tightly scoped
PostgreSQL budget reader capability is installed. No budget mutation routes.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy.pool import NullPool

from src.config import settings
from src.core.auth.platform_operator import PlatformOperator, require_platform_operator
from src.core.security import security_scheme


class PlatformBudgetItem(BaseModel):
    tenant_id: str
    name: str
    slug: str
    is_active: bool
    monthly_cap_usd: Decimal
    spent_usd: Decimal
    reserved_usd: Decimal
    available_usd: Decimal
    utilisation_percent: Decimal
    budget_status: str
    last_tenant_update: datetime | None = None


class PlatformBudgetPage(BaseModel):
    items: list[PlatformBudgetItem]
    total: int
    limit: int
    offset: int
    period_key: str


router = APIRouter(
    prefix="/platform/budgets",
    tags=["Platform budgets"],
    dependencies=[Depends(security_scheme), Depends(require_platform_operator)],
)


def budget_owner_only(operator: PlatformOperator = Depends(require_platform_operator)) -> PlatformOperator:
    """C2.6's optional allowlist is mandatory and singular for this page."""
    allowlist = settings.platform_operator_user_ids
    if len(allowlist) != 1 or operator.clerk_user_id != allowlist[0]:
        raise HTTPException(status_code=403, detail="Not authorized")
    return operator


def _safe_search(term: str) -> str:
    """Literal search: user wildcards cannot turn a name search into a scan."""
    return "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _d(value: object) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.000001"))


def _item(row: dict[str, object]) -> PlatformBudgetItem:
    """Count tenant/bucket counters conservatively, never add them twice."""
    owner_cap = _d(row["owner_cap"])
    bucket_cap = _d(row["bucket_cap"]) if row["bucket_cap"] is not None else None
    cap = min(owner_cap, bucket_cap) if bucket_cap is not None else owner_cap
    spent = max(_d(row["tenant_spent"]), _d(row["bucket_spent"]))
    reserved = max(_d(row["tenant_reserved"]), _d(row["bucket_reserved"]))
    # UNKNOWN is already a held reservation in the shared tenant counter.
    available = max(Decimal("0"), cap - spent - reserved)
    used = spent + reserved
    percent = (used * 100 / cap).quantize(Decimal("0.01")) if cap > 0 else Decimal("100")
    diverged = (bucket_cap is not None and (
        _d(row["tenant_spent"]) != _d(row["bucket_spent"])
        or _d(row["tenant_reserved"]) != _d(row["bucket_reserved"])
    ))
    status = "NO_TENANT_BUCKET" if bucket_cap is None else (
        "COUNTERS_DIVERGED" if diverged else "RECONCILED"
    )
    last_updated = row.get("updated_at")
    return PlatformBudgetItem(
        tenant_id=str(row["tenant_id"]),
        name=str(row["name"]),
        slug=str(row["slug"]),
        is_active=bool(row["is_active"]),
        monthly_cap_usd=cap,
        spent_usd=spent,
        reserved_usd=reserved,
        available_usd=available,
        utilisation_percent=percent,
        budget_status=status,
        last_tenant_update=last_updated if isinstance(last_updated, datetime) else None,
    )


@asynccontextmanager
async def _budget_read_connection() -> AsyncIterator[AsyncConnection]:
    """No fallback to DATABASE_URL/ADMIN_OPS_DATABASE_URL, ever.

    Dedicated principal is checked against PostgreSQL catalog on every call.
    No persistent credential or grants are provisioned by this code.
    """
    url = settings.platform_budget_read_database_url
    if not url or not url.startswith(("postgresql://", "postgresql+asyncpg://")):
        raise HTTPException(status_code=503, detail="Budget read capability unavailable")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = None
    try:
        engine = create_async_engine(
            url, poolclass=NullPool, echo=False,
            connect_args={"statement_cache_size": 0},
        )
        async with engine.connect() as conn, conn.begin():
                await conn.execute(text("SET TRANSACTION READ ONLY"))
                # The check is intentionally strict, and fails closed if the
                # capability role/table does not exist or has broader grants.
                checks = (await conn.execute(text("""
                    SELECT r.rolcanlogin, r.rolsuper, r.rolbypassrls,
                           r.rolcreaterole, r.rolcreatedb,
                           session_user = current_user AS same_principal,
                           pg_has_role(current_user,
                             'c2pro_platform_budget_reader', 'member') AS has_cap,
                           EXISTS (
                             SELECT 1 FROM pg_auth_members m
                             JOIN pg_roles parent ON parent.oid = m.roleid
                             WHERE m.member = (SELECT oid FROM pg_roles
                                               WHERE rolname = current_user)
                               AND parent.rolname <> 'c2pro_platform_budget_reader'
                           ) AS extra_roles,
                           EXISTS (
                             SELECT 1 FROM pg_class c
                             WHERE c.relname IN ('tenants', 'n4_budget_buckets')
                               AND c.relnamespace = 'public'::regnamespace
                               AND c.relowner = (SELECT oid FROM pg_roles
                                                 WHERE rolname = current_user)
                           ) AS owns_tables,
                           has_database_privilege(current_user, current_database(), 'CREATE')
                             AS create_db,
                           has_schema_privilege(current_user, 'public', 'CREATE')
                             AS create_schema,
                           has_table_privilege(current_user, 'public.tenants', 'INSERT,UPDATE,DELETE')
                             AS writable_tenants,
                           has_table_privilege(current_user, 'public.n4_budget_buckets', 'INSERT,UPDATE,DELETE')
                             AS writable_buckets,
                           has_column_privilege(current_user, 'public.tenants', 'id', 'SELECT')
                             AS select_tenants,
                           has_column_privilege(current_user, 'public.n4_budget_buckets', 'cap_usd', 'SELECT')
                             AS select_buckets
                    FROM pg_roles r WHERE r.rolname = current_user
                """))).mappings().one()
                if (not checks["rolcanlogin"] or checks["rolsuper"] or
                    checks["rolbypassrls"] or checks["rolcreaterole"] or
                    checks["rolcreatedb"] or not checks["same_principal"] or
                    not checks["has_cap"] or checks["extra_roles"] or
                    checks["owns_tables"] or checks["create_db"] or
                    checks["create_schema"] or checks["writable_tenants"] or
                    checks["writable_buckets"] or not checks["select_tenants"] or
                    not checks["select_buckets"]):
                    raise RuntimeError("budget database capability check failed")
                yield conn
    except HTTPException:
        raise
    except (RuntimeError, SQLAlchemyError, ValueError, TypeError):
        # Do not disclose database configuration or query details.
        raise HTTPException(status_code=503, detail="Budget read capability unavailable") from None
    finally:
        if engine is not None:
            await engine.dispose()


@router.get("", response_model=PlatformBudgetPage)
async def list_platform_budgets(
    query: str = Query(default="", max_length=100),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    operator: PlatformOperator = Depends(budget_owner_only),
) -> PlatformBudgetPage:
    """One page, all tenant budgets. Not a spending authorisation or edit API."""
    del operator  # authorization is checked before DB access
    period = datetime.now(UTC).strftime("%Y-%m")
    bind = {"period": period, "search": _safe_search(query.strip()), "limit": limit, "offset": offset}
    async with _budget_read_connection() as conn:
        # Search and pagination live on the server; no tenant identifiers accepted.
        total = (await conn.execute(text("""
            SELECT count(*) FROM public.tenants t
             WHERE (t.name ILIKE :search ESCAPE '\' OR t.slug ILIKE :search ESCAPE '\')
        """), bind)).scalar_one()
        rows = (await conn.execute(text("""
            SELECT t.id AS tenant_id, t.name, t.slug, t.is_active, t.updated_at,
                   t.ai_budget_monthly AS owner_cap,
                   t.ai_spend_current AS tenant_spent,
                   t.ai_spend_reserved_usd AS tenant_reserved,
                   b.cap_usd AS bucket_cap,
                   b.spent_usd AS bucket_spent,
                   b.reserved_usd AS bucket_reserved
              FROM public.tenants t
              LEFT JOIN public.n4_budget_buckets b
                ON b.tenant_id = t.id AND b.scope_kind = 'TENANT'
               AND b.scope_id = t.id AND b.period_key = :period
             WHERE (t.name ILIKE :search ESCAPE '\' OR t.slug ILIKE :search ESCAPE '\')
             ORDER BY t.name COLLATE "C", t.id
             LIMIT :limit OFFSET :offset
        """), bind)).mappings().all()
    return PlatformBudgetPage(
        items=[_item(dict(r)) for r in rows],
        total=total, limit=limit, offset=offset, period_key=period,
    )
