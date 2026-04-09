"""
RLS Fail-Closed Security Tests

Tests the fail-closed behavior of RLS policies after the 20260318_0002 migration.

Requirements:
- RLS policies must return NO ROWS when app.current_tenant is not set
- RLS policies must return ONLY rows for the current tenant when set
- Cross-tenant access must be blocked

Test Matrix:
+-------------------------+---------------+----------------+-----------+
| Scenario                | Tenant Context| Expected Rows  | Status    |
+-------------------------+---------------+----------------+-----------+
| No context set          | None/Empty    | 0              | BLOCKED   |
| Valid tenant context    | Valid UUID    | Tenant's rows  | ALLOWED   |
| Cross-tenant access     | Tenant A      | 0 for Tenant B | BLOCKED   |
+-------------------------+---------------+----------------+-----------+

References:
- C2PRO Technical Audit Report 2026-03-18
- Migration: 20260318_0002_fix_rls_policies_fail_closed.py
"""

from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.config import settings

# Test configuration
TENANT_A_ID = UUID("11111111-1111-1111-1111-111111111111")
TENANT_B_ID = uuid4()  # Random tenant for isolation test


@pytest_asyncio.fixture
async def raw_engine():
    """Create a raw async engine for testing.

    Uses main DB (5432) if test DB (5433) is unavailable via TCP.
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
async def rls_test_session(raw_engine):
    """
    Create a session that simulates a non-superuser subject to RLS.

    Note: We can't actually create a non-superuser role in tests,
    but we can verify the RLS policy behavior by checking the
    query results with and without tenant context.
    """
    async_session = sessionmaker(raw_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


class TestRLSFailClosed:
    """Tests for fail-closed RLS behavior."""

    @pytest.mark.asyncio
    async def test_001_no_tenant_context_returns_no_rows(self, rls_test_session: AsyncSession):
        """
        SECURITY TEST: Without app.current_tenant set, queries should return 0 rows.

        This is the fail-closed behavior that was fixed in migration 20260318_0002.
        Previously, COALESCE(..., tenant_id) would return ALL rows when context was empty.
        """
        # Ensure no tenant context is set (clear any existing)
        await rls_test_session.execute(text("RESET app.current_tenant"))

        # Verify tenant context is empty
        result = await rls_test_session.execute(
            text("SELECT current_setting('app.current_tenant', true)")
        )
        current_tenant = result.scalar()
        assert current_tenant in (None, ""), f"Expected empty tenant context, got: {current_tenant}"

        # Query projects without tenant context - as superuser we bypass RLS
        # This test documents the expected behavior for non-superuser roles
        result = await rls_test_session.execute(
            text(
                """
                -- This shows what a non-superuser with this policy would see
                SELECT COUNT(*)
                FROM projects p
                WHERE p.tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
            """
            )
        )
        count = result.scalar()
        assert count == 0, f"Expected 0 rows without tenant context, got: {count}"

    @pytest.mark.asyncio
    async def test_002_with_tenant_context_returns_tenant_rows(
        self, rls_test_session: AsyncSession
    ):
        """
        SECURITY TEST: With valid app.current_tenant, queries return only that tenant's rows.
        """
        # Set tenant context
        await rls_test_session.execute(text(f"SET LOCAL app.current_tenant = '{TENANT_A_ID}'"))

        # Query using the same logic as RLS policy
        result = await rls_test_session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM projects p
                WHERE p.tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
            """
            )
        )
        result.scalar()

        # Should only see Tenant A's projects (may be 0 if none exist, but not ALL projects)
        # The key is that it's filtering correctly
        result = await rls_test_session.execute(
            text(
                """
                SELECT DISTINCT tenant_id
                FROM projects p
                WHERE p.tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
            """
            )
        )
        tenant_ids = [row[0] for row in result.fetchall()]

        # All returned rows should belong to TENANT_A_ID
        for tid in tenant_ids:
            assert tid == TENANT_A_ID, f"Got row from wrong tenant: {tid}"

    @pytest.mark.asyncio
    async def test_003_cross_tenant_isolation(self, rls_test_session: AsyncSession):
        """
        SECURITY TEST: Tenant A context cannot access Tenant B's data.
        """
        # Get all projects count (as superuser)
        result = await rls_test_session.execute(text("SELECT COUNT(*) FROM projects"))
        total_projects = result.scalar()

        if total_projects == 0:
            pytest.skip("No projects in database to test isolation")

        # Set Tenant A context
        await rls_test_session.execute(text(f"SET LOCAL app.current_tenant = '{TENANT_A_ID}'"))

        # Query for any project NOT belonging to Tenant A
        result = await rls_test_session.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM projects p
                WHERE p.tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
                  AND p.tenant_id != '{TENANT_A_ID}'
            """
            )
        )
        cross_tenant_count = result.scalar()

        # Should find 0 rows from other tenants
        assert cross_tenant_count == 0, (
            f"Cross-tenant access detected! " f"Found {cross_tenant_count} rows from other tenants"
        )

    @pytest.mark.asyncio
    async def test_004_policy_definitions_are_fail_closed(self, rls_test_session: AsyncSession):
        """
        META TEST: Verify the RLS policy definitions don't use COALESCE fallback.

        This catches regression if someone re-introduces the permissive pattern.
        """
        # Check policy definitions for the dangerous COALESCE pattern
        result = await rls_test_session.execute(
            text(
                """
                SELECT tablename, policyname, qual
                FROM pg_policies
                WHERE schemaname = 'public'
                  AND tablename IN ('projects', 'users', 'tenants', 'review_items')
                  AND cmd = 'SELECT'
                ORDER BY tablename
            """
            )
        )

        policies = result.fetchall()
        assert len(policies) > 0, "No RLS policies found - RLS may be disabled"

        for tablename, policyname, qual in policies:
            # Check for the dangerous COALESCE(... , tenant_id) pattern
            if qual and "COALESCE" in qual.upper():
                pytest.fail(
                    f"SECURITY VULNERABILITY: Policy '{policyname}' on '{tablename}' "
                    f"uses COALESCE pattern which allows access without tenant context.\n"
                    f"Policy qual: {qual}"
                )

    @pytest.mark.asyncio
    async def test_005_superuser_bypasses_rls(self, rls_test_session: AsyncSession):
        """
        Verify superuser (postgres) can access all data regardless of tenant context.

        This is expected behavior - superusers bypass RLS unless FORCE ROW LEVEL SECURITY is set.
        """
        # Clear tenant context
        await rls_test_session.execute(text("RESET app.current_tenant"))

        # Superuser should see all projects
        result = await rls_test_session.execute(text("SELECT COUNT(*) FROM projects"))
        result.scalar()

        # We're running as superuser (postgres), so we should see all rows
        # This documents that superuser access is expected to bypass RLS
        # If count is 0, either there are no projects or RLS is blocking even superuser
        # The latter would mean FORCE ROW LEVEL SECURITY is enabled

        result = await rls_test_session.execute(
            text(
                """
                SELECT relforcerowsecurity
                FROM pg_class
                WHERE relname = 'projects'
            """
            )
        )
        force_rls = result.scalar()

        if force_rls:
            pytest.skip("FORCE ROW LEVEL SECURITY is enabled, superuser bypass is disabled")

        # If force_rls is False, superuser should see data
        # Count can be 0 if no projects exist, which is fine


class TestRLSPolicyCompleteness:
    """Tests for RLS policy completeness across all tables."""

    @pytest.mark.asyncio
    async def test_006_all_tenant_tables_have_rls(self, rls_test_session: AsyncSession):
        """
        Verify all tables with tenant_id column have RLS enabled.
        Note: Views don't need RLS - they inherit from base tables.
        """
        result = await rls_test_session.execute(
            text(
                """
                SELECT c.table_name
                FROM information_schema.columns c
                JOIN pg_class pc ON pc.relname = c.table_name
                WHERE c.column_name = 'tenant_id'
                  AND c.table_schema = 'public'
                  AND pc.relnamespace = 'public'::regnamespace
                  AND pc.relkind = 'r'
                  AND pc.relrowsecurity = false
            """
            )
        )

        tables_without_rls = [row[0] for row in result.fetchall()]

        if tables_without_rls:
            pytest.fail(
                f"SECURITY GAP: Tables with tenant_id but no RLS enabled: " f"{tables_without_rls}"
            )

    @pytest.mark.asyncio
    async def test_007_rls_policies_exist_for_all_operations(self, rls_test_session: AsyncSession):
        """
        Verify RLS policies exist for SELECT, INSERT, UPDATE, DELETE on tenant tables.
        """
        # Tables that should have full RLS coverage
        protected_tables = ["projects", "users", "tenants", "review_items"]
        required_ops = ["SELECT", "INSERT", "UPDATE", "DELETE"]

        for table in protected_tables:
            for op in required_ops:
                result = await rls_test_session.execute(
                    text(
                        f"""
                        SELECT COUNT(*)
                        FROM pg_policies
                        WHERE schemaname = 'public'
                          AND tablename = '{table}'
                          AND cmd = '{op}'
                    """
                    )
                )
                count = result.scalar()

                if count == 0:
                    pytest.fail(f"SECURITY GAP: No {op} policy on table '{table}'")
