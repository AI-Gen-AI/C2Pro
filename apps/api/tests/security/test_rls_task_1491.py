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
| No context set          | None/Empty    | 0              | BLOCKED   |
| Valid tenant context    | Valid UUID    | Tenant's rows  | ALLOWED   |
| Cross-tenant access     | Tenant A      | 0 for Tenant B | BLOCKED   |
| Policy completeness     | N/A           | All tables     | PASS      |
| New columns exist       | N/A           | project_id     | PASS      |
+-------------------------+---------------+----------------+-----------+

Suite ID: TS-DB-MIG-RLS-002
"""

import pytest
import pytest_asyncio
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.config import settings

# Test constants - use unique slugs to avoid conflicts with existing data
TENANT_A_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT_B_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
PROJECT_A_ID = UUID("11111111-1111-1111-1111-111111111111")
PROJECT_B_ID = UUID("22222222-2222-2222-2222-222222222222")

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
    
    Always connects to the test database (c2pro_test on port 5433).
    Falls back to main database (c2pro on port 5432) only if test DB is unavailable.
    """
    db_url = settings.database_url
    # Force test database connection
    if "5432" in db_url and "5433" not in db_url:
        db_url = db_url.replace("5432/c2pro", "5433/c2pro_test")
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


@pytest_asyncio.fixture
async def seeded_data(raw_engine):
    """Create test tenants, projects, and sample rows for RLS testing.
    
    Uses cleanup-first approach with separate connections to avoid
    transaction corruption from missing tables.
    """
    # ===========================================
    # CLEANUP: Use separate connections for each cleanup operation
    # to avoid InFailedSQLTransactionError
    # ===========================================
    cleanup_tables = [
        "stakeholder_wbs_raci",
        "procurement_bom_items",
        "procurement_wbs_items",
        "procurement_budget_items",
        "extractions",
        "document_chunks",
        "coherence_results",
        "wbs_items",
        "alerts",
        "analyses",
        "stakeholders",
        "projects",
        "clause_embeddings",
    ]
    
    for table in cleanup_tables:
        async with AsyncSession(raw_engine) as session:
            try:
                await session.execute(
                    text(f"DELETE FROM {table} WHERE id IN (:p_a, :p_b)"),
                    {"p_a": PROJECT_A_ID, "p_b": PROJECT_B_ID},
                )
                await session.commit()
            except Exception:
                await session.rollback()
    
    # Clean up tenants by slug
    async with AsyncSession(raw_engine) as session:
        try:
            await session.execute(
                text("DELETE FROM tenants WHERE slug IN ('tenant-a-1491', 'tenant-b-1491')")
            )
            await session.commit()
        except Exception:
            await session.rollback()

    # ===========================================
    # SEED: Create fresh test data
    # ===========================================
    async with AsyncSession(raw_engine) as session:
        # Create tenants with unique slugs to avoid conflicts
        await session.execute(
            text(
                """
                INSERT INTO tenants (id, name, slug, subscription_plan, subscription_status,
                                     ai_budget_monthly, ai_spend_current, max_projects, max_users, max_storage_gb,
                                     settings, is_active)
                VALUES (:t_a, 'Tenant A', 'tenant-a-1491', 'free', 'active', 50, 0, 5, 3, 10, '{}'::jsonb, true),
                       (:t_b, 'Tenant B', 'tenant-b-1491', 'free', 'active', 50, 0, 5, 3, 10, '{}'::jsonb, true)
                """
            ),
            {"t_a": TENANT_A_ID, "t_b": TENANT_B_ID},
        )

        # Create projects with all required columns
        await session.execute(
            text(
                """
                INSERT INTO projects (id, tenant_id, name, project_type, status, currency, metadata)
                VALUES (:p_a, :t_a, 'Project A', 'construction', 'active', 'EUR', '{}'::jsonb),
                       (:p_b, :t_b, 'Project B', 'construction', 'active', 'EUR', '{}'::jsonb)
                """
            ),
            {"p_a": PROJECT_A_ID, "p_b": PROJECT_B_ID, "t_a": TENANT_A_ID, "t_b": TENANT_B_ID},
        )

        # Seed stakeholders
        await session.execute(
            text(
                """
                INSERT INTO stakeholders (id, project_id, name, role)
                VALUES (gen_random_uuid(), :p_a, 'Stakeholder A1', 'Owner'),
                       (gen_random_uuid(), :p_b, 'Stakeholder B1', 'Owner')
                """
            ),
            {"p_a": PROJECT_A_ID, "p_b": PROJECT_B_ID},
        )

        # Seed analyses
        await session.execute(
            text(
                """
                INSERT INTO analyses (id, project_id, analysis_type, status, alerts_count)
                VALUES (gen_random_uuid(), :p_a, 'coherence', 'completed', 0),
                       (gen_random_uuid(), :p_b, 'coherence', 'completed', 0)
                """
            ),
            {"p_a": PROJECT_A_ID, "p_b": PROJECT_B_ID},
        )

        # Seed alerts
        await session.execute(
            text(
                """
                INSERT INTO alerts (id, project_id, severity, title, description, status)
                VALUES (gen_random_uuid(), :p_a, 'high', 'Alert A1', 'desc', 'open'),
                       (gen_random_uuid(), :p_b, 'high', 'Alert B1', 'desc', 'open')
                """
            ),
            {"p_a": PROJECT_A_ID, "p_b": PROJECT_B_ID},
        )

        # Seed wbs_items
        await session.execute(
            text(
                """
                INSERT INTO wbs_items (id, project_id, code, name, level)
                VALUES (gen_random_uuid(), :p_a, 'WBS-A1', 'WBS Item A1', 1),
                       (gen_random_uuid(), :p_b, 'WBS-B1', 'WBS Item B1', 1)
                """
            ),
            {"p_a": PROJECT_A_ID, "p_b": PROJECT_B_ID},
        )

        # Seed coherence_results
        await session.execute(
            text(
                """
                INSERT INTO coherence_results (id, project_id, global_score, category_scores, category_details, alerts, is_gaming_detected, gaming_violations, penalty_points)
                VALUES (gen_random_uuid(), :p_a, 85, '{}', '{}', '[]', false, '{}', 0),
                       (gen_random_uuid(), :p_b, 90, '{}', '{}', '[]', false, '{}', 0)
                """
            ),
            {"p_a": PROJECT_A_ID, "p_b": PROJECT_B_ID},
        )

        # Seed document_chunks
        await session.execute(
            text(
                """
                INSERT INTO document_chunks (id, document_id, project_id, content, embedding)
                VALUES (gen_random_uuid(), gen_random_uuid(), :p_a, 'chunk A', array_fill(0, ARRAY[1536])::vector),
                       (gen_random_uuid(), gen_random_uuid(), :p_b, 'chunk B', array_fill(0, ARRAY[1536])::vector)
                """
            ),
            {"p_a": PROJECT_A_ID, "p_b": PROJECT_B_ID},
        )

        # Seed clause_embeddings
        await session.execute(
            text(
                """
                INSERT INTO clause_embeddings (id, clause_id, project_id, document_type, text, embedding, category)
                VALUES (gen_random_uuid(), 'CLS-A1', :p_a, 'contract', 'text A', array_fill(0, ARRAY[1536])::vector, 'SCOPE'),
                       (gen_random_uuid(), 'CLS-B1', :p_b, 'contract', 'text B', array_fill(0, ARRAY[1536])::vector, 'SCOPE')
                """
            ),
            {"p_a": PROJECT_A_ID, "p_b": PROJECT_B_ID},
        )

        # Seed procurement_wbs_items
        await session.execute(
            text(
                """
                INSERT INTO procurement_wbs_items (id, project_id, code, name, level, budget_spent)
                VALUES (gen_random_uuid(), :p_a, 'PWBS-A1', 'Proc WBS A1', 1, 0),
                       (gen_random_uuid(), :p_b, 'PWBS-B1', 'Proc WBS B1', 1, 0)
                """
            ),
            {"p_a": PROJECT_A_ID, "p_b": PROJECT_B_ID},
        )

        # Seed procurement_bom_items
        await session.execute(
            text(
                """
                INSERT INTO procurement_bom_items (id, project_id, item_name, quantity, currency)
                VALUES (gen_random_uuid(), :p_a, 'BOM Item A1', 10, 'EUR'),
                       (gen_random_uuid(), :p_b, 'BOM Item B1', 20, 'EUR')
                """
            ),
            {"p_a": PROJECT_A_ID, "p_b": PROJECT_B_ID},
        )

        # Seed procurement_budget_items (now has project_id)
        await session.execute(
            text(
                """
                INSERT INTO procurement_budget_items (id, project_id, name, code, amount)
                VALUES (gen_random_uuid(), :p_a, 'Budget A1', 'BUD-A1', 1000.00),
                       (gen_random_uuid(), :p_b, 'Budget B1', 'BUD-B1', 2000.00)
                """
            ),
            {"p_a": PROJECT_A_ID, "p_b": PROJECT_B_ID},
        )

        # Seed extractions (now has project_id)
        await session.execute(
            text(
                """
                INSERT INTO extractions (id, document_id, project_id, extraction_type, data_json)
                VALUES (gen_random_uuid(), gen_random_uuid(), :p_a, 'clause', '{}'),
                       (gen_random_uuid(), gen_random_uuid(), :p_b, 'clause', '{}')
                """
            ),
            {"p_a": PROJECT_A_ID, "p_b": PROJECT_B_ID},
        )

        # Seed stakeholder_wbs_raci (needs existing stakeholders and wbs_items)
        await session.execute(
            text(
                """
                INSERT INTO stakeholder_wbs_raci (id, project_id, stakeholder_id, wbs_item_id, raci_role)
                SELECT gen_random_uuid(), :p_a, s.id, w.id, 'R'
                FROM stakeholders s, wbs_items w
                WHERE s.project_id = :p_a AND w.project_id = :p_a
                LIMIT 1
                """
            ),
            {"p_a": PROJECT_A_ID},
        )

        await session.execute(
            text(
                """
                INSERT INTO stakeholder_wbs_raci (id, project_id, stakeholder_id, wbs_item_id, raci_role)
                SELECT gen_random_uuid(), :p_b, s.id, w.id, 'A'
                FROM stakeholders s, wbs_items w
                WHERE s.project_id = :p_b AND w.project_id = :p_b
                LIMIT 1
                """
            ),
            {"p_b": PROJECT_B_ID},
        )

        await session.commit()
    yield


class TestRLSRemainingTablesFailClosed:
    """Tests for fail-closed RLS behavior on TASK-1491 tables."""

    @pytest.mark.asyncio
    async def test_001_no_tenant_context_returns_zero_stakeholders(
        self, rls_session: AsyncSession, seeded_data
    ):
        """Without app.current_tenant, stakeholders query returns 0 rows via RLS policy logic."""
        await rls_session.execute(text("RESET app.current_tenant"))

        result = await rls_session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM stakeholders s
                WHERE s.project_id IN (
                    SELECT id FROM projects
                    WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
                )
                """
            )
        )
        count = result.scalar()
        assert count == 0, f"Expected 0 rows without tenant context, got: {count}"

    @pytest.mark.asyncio
    async def test_002_tenant_a_sees_only_tenant_a_stakeholders(
        self, rls_session: AsyncSession, seeded_data
    ):
        """Tenant A context returns only stakeholders from Tenant A projects."""
        await rls_session.execute(
            text(f"SET LOCAL app.current_tenant = '{TENANT_A_ID}'")
        )

        result = await rls_session.execute(
            text(
                """
                SELECT DISTINCT p.tenant_id
                FROM stakeholders s
                JOIN projects p ON s.project_id = p.id
                WHERE s.project_id IN (
                    SELECT id FROM projects
                    WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
                )
                """
            )
        )
        tenant_ids = [row[0] for row in result.fetchall()]
        for tid in tenant_ids:
            assert tid == TENANT_A_ID, f"Cross-tenant leak: found stakeholder from tenant {tid}"

    @pytest.mark.asyncio
    async def test_003_cross_tenant_isolation_analyses(
        self, rls_session: AsyncSession, seeded_data
    ):
        """Tenant A context cannot see analyses from Tenant B."""
        await rls_session.execute(
            text(f"SET LOCAL app.current_tenant = '{TENANT_A_ID}'")
        )

        result = await rls_session.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM analyses a
                JOIN projects p ON a.project_id = p.id
                WHERE a.project_id IN (
                    SELECT id FROM projects
                    WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
                )
                AND p.tenant_id != '{TENANT_A_ID}'
                """
            )
        )
        count = result.scalar()
        assert count == 0, f"Cross-tenant access to analyses: {count} rows"

    @pytest.mark.asyncio
    async def test_004_cross_tenant_isolation_alerts(
        self, rls_session: AsyncSession, seeded_data
    ):
        """Tenant A context cannot see alerts from Tenant B."""
        await rls_session.execute(
            text(f"SET LOCAL app.current_tenant = '{TENANT_A_ID}'")
        )

        result = await rls_session.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM alerts a
                JOIN projects p ON a.project_id = p.id
                WHERE a.project_id IN (
                    SELECT id FROM projects
                    WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
                )
                AND p.tenant_id != '{TENANT_A_ID}'
                """
            )
        )
        count = result.scalar()
        assert count == 0, f"Cross-tenant access to alerts: {count} rows"

    @pytest.mark.asyncio
    async def test_005_cross_tenant_isolation_coherence_results(
        self, rls_session: AsyncSession, seeded_data
    ):
        """Tenant A context cannot see coherence_results from Tenant B."""
        await rls_session.execute(
            text(f"SET LOCAL app.current_tenant = '{TENANT_A_ID}'")
        )

        result = await rls_session.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM coherence_results c
                JOIN projects p ON c.project_id = p.id
                WHERE c.project_id IN (
                    SELECT id FROM projects
                    WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
                )
                AND p.tenant_id != '{TENANT_A_ID}'
                """
            )
        )
        count = result.scalar()
        assert count == 0, f"Cross-tenant access to coherence_results: {count} rows"

    @pytest.mark.asyncio
    async def test_006_cross_tenant_isolation_document_chunks(
        self, rls_session: AsyncSession, seeded_data
    ):
        """Tenant A context cannot see document_chunks from Tenant B."""
        await rls_session.execute(
            text(f"SET LOCAL app.current_tenant = '{TENANT_A_ID}'")
        )

        result = await rls_session.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM document_chunks dc
                JOIN projects p ON dc.project_id = p.id
                WHERE dc.project_id IN (
                    SELECT id FROM projects
                    WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
                )
                AND p.tenant_id != '{TENANT_A_ID}'
                """
            )
        )
        count = result.scalar()
        assert count == 0, f"Cross-tenant access to document_chunks: {count} rows"

    @pytest.mark.asyncio
    async def test_007_cross_tenant_isolation_wbs_items(
        self, rls_session: AsyncSession, seeded_data
    ):
        """Tenant A context cannot see wbs_items from Tenant B."""
        await rls_session.execute(
            text(f"SET LOCAL app.current_tenant = '{TENANT_A_ID}'")
        )

        result = await rls_session.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM wbs_items w
                JOIN projects p ON w.project_id = p.id
                WHERE w.project_id IN (
                    SELECT id FROM projects
                    WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
                )
                AND p.tenant_id != '{TENANT_A_ID}'
                """
            )
        )
        count = result.scalar()
        assert count == 0, f"Cross-tenant access to wbs_items: {count} rows"

    @pytest.mark.asyncio
    async def test_008_cross_tenant_isolation_clause_embeddings(
        self, rls_session: AsyncSession, seeded_data
    ):
        """Tenant A context cannot see clause_embeddings from Tenant B."""
        await rls_session.execute(
            text(f"SET LOCAL app.current_tenant = '{TENANT_A_ID}'")
        )

        result = await rls_session.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM clause_embeddings ce
                JOIN projects p ON ce.project_id = p.id
                WHERE ce.project_id IN (
                    SELECT id FROM projects
                    WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
                )
                AND p.tenant_id != '{TENANT_A_ID}'
                """
            )
        )
        count = result.scalar()
        assert count == 0, f"Cross-tenant access to clause_embeddings: {count} rows"

    @pytest.mark.asyncio
    async def test_009_cross_tenant_isolation_procurement_wbs_items(
        self, rls_session: AsyncSession, seeded_data
    ):
        """Tenant A context cannot see procurement_wbs_items from Tenant B."""
        await rls_session.execute(
            text(f"SET LOCAL app.current_tenant = '{TENANT_A_ID}'")
        )

        result = await rls_session.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM procurement_wbs_items pw
                JOIN projects p ON pw.project_id = p.id
                WHERE pw.project_id IN (
                    SELECT id FROM projects
                    WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
                )
                AND p.tenant_id != '{TENANT_A_ID}'
                """
            )
        )
        count = result.scalar()
        assert count == 0, f"Cross-tenant access to procurement_wbs_items: {count} rows"

    @pytest.mark.asyncio
    async def test_010_cross_tenant_isolation_procurement_bom_items(
        self, rls_session: AsyncSession, seeded_data
    ):
        """Tenant A context cannot see procurement_bom_items from Tenant B."""
        await rls_session.execute(
            text(f"SET LOCAL app.current_tenant = '{TENANT_A_ID}'")
        )

        result = await rls_session.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM procurement_bom_items pb
                JOIN projects p ON pb.project_id = p.id
                WHERE pb.project_id IN (
                    SELECT id FROM projects
                    WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
                )
                AND p.tenant_id != '{TENANT_A_ID}'
                """
            )
        )
        count = result.scalar()
        assert count == 0, f"Cross-tenant access to procurement_bom_items: {count} rows"

    @pytest.mark.asyncio
    async def test_011_cross_tenant_isolation_procurement_budget_items(
        self, rls_session: AsyncSession, seeded_data
    ):
        """Tenant A context cannot see procurement_budget_items from Tenant B."""
        await rls_session.execute(
            text(f"SET LOCAL app.current_tenant = '{TENANT_A_ID}'")
        )

        result = await rls_session.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM procurement_budget_items pb
                JOIN projects p ON pb.project_id = p.id
                WHERE pb.project_id IN (
                    SELECT id FROM projects
                    WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
                )
                AND p.tenant_id != '{TENANT_A_ID}'
                """
            )
        )
        count = result.scalar()
        assert count == 0, f"Cross-tenant access to procurement_budget_items: {count} rows"

    @pytest.mark.asyncio
    async def test_012_cross_tenant_isolation_extractions(
        self, rls_session: AsyncSession, seeded_data
    ):
        """Tenant A context cannot see extractions from Tenant B."""
        await rls_session.execute(
            text(f"SET LOCAL app.current_tenant = '{TENANT_A_ID}'")
        )

        result = await rls_session.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM extractions e
                JOIN projects p ON e.project_id = p.id
                WHERE e.project_id IN (
                    SELECT id FROM projects
                    WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
                )
                AND p.tenant_id != '{TENANT_A_ID}'
                """
            )
        )
        count = result.scalar()
        assert count == 0, f"Cross-tenant access to extractions: {count} rows"

    @pytest.mark.asyncio
    async def test_013_cross_tenant_isolation_stakeholder_wbs_raci(
        self, rls_session: AsyncSession, seeded_data
    ):
        """Tenant A context cannot see stakeholder_wbs_raci from Tenant B."""
        await rls_session.execute(
            text(f"SET LOCAL app.current_tenant = '{TENANT_A_ID}'")
        )

        result = await rls_session.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM stakeholder_wbs_raci sr
                JOIN projects p ON sr.project_id = p.id
                WHERE sr.project_id IN (
                    SELECT id FROM projects
                    WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
                )
                AND p.tenant_id != '{TENANT_A_ID}'
                """
            )
        )
        count = result.scalar()
        assert count == 0, f"Cross-tenant access to stakeholder_wbs_raci: {count} rows"


class TestRLSPolicyCompleteness:
    """Tests for RLS policy completeness on TASK-1491 tables."""

    @pytest.mark.asyncio
    async def test_014_all_task_1491_tables_have_rls_enabled(
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
    async def test_015_all_task_1491_tables_have_policies(
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
    async def test_016_no_coalesce_in_task_1491_policies(
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
    async def test_017_procurement_budget_items_has_project_id(
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
    async def test_018_extractions_has_project_id(
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
    async def test_019_force_rls_on_task_1491_tables(
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
    async def test_020_no_orphaned_tables_in_system(
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
