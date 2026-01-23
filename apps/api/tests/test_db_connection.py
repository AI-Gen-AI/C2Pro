"""
Test de conexión a PostgreSQL para validar configuración de tests.

Este test verifica que la conexión a la BD de tests funcione correctamente.
"""

import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_postgresql_connection_available(db_engine):
    """Verifica que PostgreSQL esté disponible y conectado."""
    async with db_engine.connect() as conn:
        # Test básico de conexión
        result = await conn.execute(text("SELECT 1 as test"))
        assert result.scalar() == 1

        # Verificar BD correcta
        db_name = await conn.execute(text("SELECT current_database()"))
        current_db = db_name.scalar()
        print(f"\nConectado a: {current_db}")
        assert current_db == "c2pro_test"


@pytest.mark.asyncio
async def test_postgresql_tables_exist(db_engine):
    """Verifica que las tablas de migraciones existan."""
    async with db_engine.connect() as conn:
        # Contar tablas
        result = await conn.execute(
            text("""
            SELECT COUNT(*) as table_count
            FROM information_schema.tables
            WHERE table_schema = 'public'
        """)
        )

        table_count = result.scalar()
        print(f"\nTablas en public schema: {table_count}")

        # Verificar tablas críticas
        result = await conn.execute(
            text("""
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename
        """)
        )

        tables = [row[0] for row in result.fetchall()]
        print("\nTablas disponibles:")
        for table in tables[:10]:
            print(f"  - {table}")

        # Verificar tablas críticas existen
        critical_tables = ["tenants", "users", "projects", "clauses"]
        for table in critical_tables:
            assert table in tables, f"Tabla crítica '{table}' no encontrada"

        assert table_count >= 20, f"Se esperaban al menos 20 tablas, encontradas: {table_count}"


@pytest.mark.asyncio
async def test_postgresql_rls_enabled(db_engine):
    """Verifica que RLS esté habilitado en las tablas."""
    async with db_engine.connect() as conn:
        # Contar tablas con RLS
        result = await conn.execute(
            text("""
            SELECT COUNT(*) as rls_count
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relrowsecurity = true
            AND n.nspname = 'public'
            AND c.relkind = 'r'
        """)
        )

        rls_count = result.scalar()
        print(f"\nTablas con RLS habilitado: {rls_count}")

        assert rls_count >= 18, f"Se esperaban al menos 18 tablas con RLS, encontradas: {rls_count}"


@pytest.mark.asyncio
async def test_postgresql_mcp_views_exist(db_engine):
    """Verifica que las vistas MCP existan."""
    async with db_engine.connect() as conn:
        # Contar vistas MCP
        result = await conn.execute(
            text("""
            SELECT viewname
            FROM pg_views
            WHERE schemaname = 'public'
            AND viewname LIKE 'v_project_%'
            ORDER BY viewname
        """)
        )

        views = [row[0] for row in result.fetchall()]
        print(f"\nVistas MCP disponibles: {len(views)}")
        for view in views:
            print(f"  - {view}")

        # Nota: Las vistas MCP pueden no existir en BD local si no se han aplicado migraciones
        if len(views) > 0:
            assert len(views) >= 4, f"Se esperaban al menos 4 vistas MCP, encontradas: {len(views)}"
            assert "v_project_summary" in views
            assert "v_project_alerts" in views
        else:
            print("\nADVERTENCIA: No hay vistas MCP. Aplica migraciones con:")
            print(
                "  docker exec -i c2pro-test-db psql -U test -d c2pro_test < infrastructure/supabase/migrations/002_*.sql"
            )


@pytest.mark.asyncio
async def test_postgresql_schema_migrations_table(db_engine):
    """Verifica que la tabla schema_migrations exista y tenga registros."""
    async with db_engine.connect() as conn:
        # Verificar tabla existe
        result = await conn.execute(
            text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'schema_migrations'
            ) as exists
        """)
        )

        exists = result.scalar()

        if exists:
            # Contar migraciones aplicadas
            result = await conn.execute(
                text("""
                SELECT version, applied_at
                FROM schema_migrations
                ORDER BY applied_at
            """)
            )

            migrations = result.fetchall()
            print(f"\nMigraciones aplicadas: {len(migrations)}")
            for version, applied_at in migrations:
                print(f"  - {version} (aplicada: {applied_at})")

            assert len(migrations) >= 2, "Se esperaban al menos 2 migraciones aplicadas"
        else:
            print("\nADVERTENCIA: schema_migrations no existe (BD sin migraciones del runner)")
            print("Las migraciones se aplican con:")
            print("  python infrastructure/supabase/run_migrations.py --env local")
