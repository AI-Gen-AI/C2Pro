"""
TASK-1491: RLS on remaining tables

Tests Row Level Security enforcement on all tables covered by migration 20260403_0002.

Tables under test:
- stakeholders, stakeholder_wbs_raci
- procurement_wbs_items, procurement_bom_items, procurement_budget_items
- analyses, alerts
- coherence_results
- document_chunks, wbs_items, clause_embeddings
- extractions

Test Matrix:
+-------------------------+---------------+----------------+-----------+
| Scenario                | Tenant Context| Expected Rows  | Status    |
+-------------------------+---------------+----------------+-----------+
| Policy completeness     | N/A           | All tables     | PASS      |
| No COALESCE pattern     | N/A           | All policies   | PASS      |
| New columns exist       | N/A           | project_id     | PASS      |
| FORCE RLS enabled       | N/A           | All tables     | PASS      |
+-------------------------+---------------+----------------+-----------+

Suite ID: TS-DB-MIG-RLS-002
"""


import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.config import settings

# All tables that should have RLS after TASK-1491
RLS_TABLES_TASK_1491 = [
    "stakeholders",
    "stakeholder_wbs_raci",
    "procurement_wbs_items",
    "procurement_bom_items",
    "procurement_budget_items",
    "analyses",
    "alerts",
    "coherence_results",
    "document_chunks",
    "wbs_items",
    "clause_embeddings",
    "extractions",
]


@pytest_asyncio.fixture
async def raw_engine():
    """Create a raw async engine for testing.

    Uses main DB (5432/c2pro) since RLS tests require the full schema.
    """
    db_url = settings.database_url
    if "5433" in db_url:
        db_url = db_url.replace("5433/c2pro_test", "5432/c2pro")
    engine = create_async_engine(
        db_url.replace("postgresql://", "postgresql+asyncpg://"),
        echo=False,
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def rls_session(raw_engine):
    """Create a session for RLS testing."""
    async_session = sessionmaker(raw_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


class TestRLSPolicyCompleteness:
    """Tests for RLS policy completeness on TASK-1491 tables."""

    @pytest.mark.asyncio
    async def test_001_all_task_1491_tables_have_rls_enabled(
        self, rls_session: AsyncSession
    ):
        """Verify all TASK-1491 tables have RLS enabled."""
        result = await rls_session.execute(
            text(
                """
                SELECT relname
                FROM pg_class
                WHERE relname = ANY(:tables)
                  AND relnamespace = 'public'::regnamespace
                  AND relkind = 'r'
                  AND relrowsecurity = false
                """
            ),
            {"tables": RLS_TABLES_TASK_1491},
        )
        tables_without_rls = [row[0] for row in result.fetchall()]
        assert not tables_without_rls, (
            f"SECURITY GAP: Tables without RLS enabled: {tables_without_rls}"
        )

    @pytest.mark.asyncio
    async def test_002_all_task_1491_tables_have_policies(
        self, rls_session: AsyncSession
    ):
        """Verify all TASK-1491 tables have at least one RLS policy."""
        result = await rls_session.execute(
            text(
                """
                SELECT tablename
                FROM pg_policies
                WHERE schemaname = 'public'
                  AND tablename = ANY(:tables)
                GROUP BY tablename
                """
            ),
            {"tables": RLS_TABLES_TASK_1491},
        )
        tables_with_policies = {row[0] for row in result.fetchall()}
        missing = set(RLS_TABLES_TASK_1491) - tables_with_policies
        assert not missing, f"SECURITY GAP: Tables without RLS policies: {missing}"

    @pytest.mark.asyncio
    async def test_003_no_coalesce_in_task_1491_policies(
        self, rls_session: AsyncSession
    ):
        """Verify no TASK-1491 policies use the dangerous COALESCE pattern."""
        result = await rls_session.execute(
            text(
                """
                SELECT tablename, policyname, qual
                FROM pg_policies
                WHERE schemaname = 'public'
                  AND tablename = ANY(:tables)
                """
            ),
            {"tables": RLS_TABLES_TASK_1491},
        )
        policies = result.fetchall()
        for tablename, policyname, qual in policies:
            if qual and "COALESCE" in qual.upper():
                pytest.fail(
                    f"SECURITY VULNERABILITY: Policy '{policyname}' on '{tablename}' "
                    f"uses COALESCE pattern.\nQual: {qual}"
                )

    @pytest.mark.asyncio
    async def test_004_procurement_budget_items_has_project_id(
        self, rls_session: AsyncSession
    ):
        """Verify procurement_budget_items now has project_id column."""
        result = await rls_session.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'procurement_budget_items'
                  AND column_name = 'project_id'
                """
            )
        )
        column = result.scalar()
        assert column == "project_id", (
            "procurement_budget_items missing project_id column - RLS cannot isolate this table"
        )

    @pytest.mark.asyncio
    async def test_005_extractions_has_project_id(
        self, rls_session: AsyncSession
    ):
        """Verify extractions now has project_id column."""
        result = await rls_session.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'extractions'
                  AND column_name = 'project_id'
                """
            )
        )
        column = result.scalar()
        assert column == "project_id", (
            "extractions missing project_id column - RLS cannot isolate this table"
        )

    @pytest.mark.asyncio
    async def test_006_force_rls_on_task_1491_tables(
        self, rls_session: AsyncSession
    ):
        """Verify FORCE ROW LEVEL SECURITY is enabled on TASK-1491 tables."""
        result = await rls_session.execute(
            text(
                """
                SELECT relname, relforcerowsecurity
                FROM pg_class
                WHERE relname = ANY(:tables)
                  AND relnamespace = 'public'::regnamespace
                  AND relkind = 'r'
                """
            ),
            {"tables": RLS_TABLES_TASK_1491},
        )
        for tablename, force_rls in result.fetchall():
            assert force_rls, f"{tablename} missing FORCE ROW LEVEL SECURITY"

    @pytest.mark.asyncio
    async def test_007_no_orphaned_tables_in_system(
        self, rls_session: AsyncSession
    ):
        """Verify no tables with project_id lack RLS protection."""
        result = await rls_session.execute(
            text(
                """
                SELECT c.table_name
                FROM information_schema.columns c
                JOIN pg_class pc ON pc.relname = c.table_name
                WHERE c.column_name = 'project_id'
                  AND c.table_schema = 'public'
                  AND pc.relnamespace = 'public'::regnamespace
                  AND pc.relkind = 'r'
                  AND pc.relrowsecurity = false
                  AND c.table_name NOT IN ('alembic_version', 'checkpoint_migrations', 'checkpoints', 'checkpoint_blobs', 'checkpoint_writes')
                """
            )
        )
        tables_without_rls = [row[0] for row in result.fetchall()]
        assert not tables_without_rls, (
            f"SECURITY GAP: Tables with project_id but no RLS: {tables_without_rls}"
        )

    @pytest.mark.asyncio
    async def test_008_all_policies_use_fail_closed_pattern(
        self, rls_session: AsyncSession
    ):
        """Verify all TASK-1491 policies use the fail-closed NULLIF pattern."""
        result = await rls_session.execute(
            text(
                """
                SELECT tablename, policyname, qual
                FROM pg_policies
                WHERE schemaname = 'public'
                  AND tablename = ANY(:tables)
                """
            ),
            {"tables": RLS_TABLES_TASK_1491},
        )
        policies = result.fetchall()
        assert len(policies) > 0, "No RLS policies found for TASK-1491 tables"

        for tablename, policyname, qual in policies:
            assert "NULLIF" in qual.upper(), (
                f"Policy '{policyname}' on '{tablename}' missing NULLIF fail-closed pattern"
            )
            assert "current_setting('app.current_tenant'" in qual, (
                f"Policy '{policyname}' on '{tablename}' not using app.current_tenant GUC"
            )

    @pytest.mark.asyncio
    async def test_009_policy_naming_convention(
        self, rls_session: AsyncSession
    ):
        """Verify all TASK-1491 policies follow naming convention."""
        result = await rls_session.execute(
            text(
                """
                SELECT tablename, policyname
                FROM pg_policies
                WHERE schemaname = 'public'
                  AND tablename = ANY(:tables)
                """
            ),
            {"tables": RLS_TABLES_TASK_1491},
        )
        policies = result.fetchall()
        for tablename, policyname in policies:
            assert "tenant_isolation" in policyname, (
                f"Policy '{policyname}' on '{tablename}' doesn't follow naming convention"
            )

    @pytest.mark.asyncio
    async def test_010_project_id_indexes_exist(
        self, rls_session: AsyncSession
    ):
        """Verify project_id indexes exist for RLS performance."""
        result = await rls_session.execute(
            text(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename IN ('procurement_budget_items', 'extractions')
                  AND indexdef LIKE '%project_id%'
                """
            )
        )
        indexes = {row[0] for row in result.fetchall()}
        assert len(indexes) >= 2, (
            f"Missing project_id indexes for RLS performance. Found: {indexes}"
        )
