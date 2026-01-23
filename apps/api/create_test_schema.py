"""
Script para crear el schema de la base de datos de test desde los modelos SQLAlchemy.

Esto asegura que el schema coincida exactamente con los modelos Python.
"""

import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Configurar variables de entorno necesarias
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5433/c2pro_test"
os.environ["SUPABASE_URL"] = "http://localhost:8000"
os.environ["SUPABASE_ANON_KEY"] = "dummy"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "dummy"
os.environ["JWT_SECRET_KEY"] = "dummy"

from src.core.database import Base

# Importar todos los modelos para que se registren en Base.metadata


async def create_schema():
    """Crea todas las tablas en la base de datos de test."""
    # Conectar a PostgreSQL de test
    database_url = "postgresql+asyncpg://test:test@localhost:5433/c2pro_test"

    engine = create_async_engine(
        database_url,
        echo=True,
        pool_pre_ping=True,
    )

    try:
        print("Creando extensiones necesarias...")
        async with engine.begin() as conn:
            # Crear extensiones necesarias
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pgcrypto"'))
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pg_trgm"'))

            # Crear función update_updated_at_column
            await conn.execute(
                text("""
                CREATE OR REPLACE FUNCTION update_updated_at_column()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $$ language 'plpgsql';
            """)
            )

            # Crear función auth.jwt() simplificada para tests
            await conn.execute(
                text("""
                CREATE SCHEMA IF NOT EXISTS auth;
            """)
            )

            await conn.execute(
                text("""
                CREATE OR REPLACE FUNCTION auth.jwt()
                RETURNS JSONB AS $$
                BEGIN
                    RETURN '{}'::JSONB;
                END;
                $$ language 'plpgsql';
            """)
            )

        print("\nCreando todas las tablas desde modelos SQLAlchemy...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        print("\nConfigurando permisos y RLS para tests...")
        async with engine.begin() as conn:
            rls_statements = [
                "ALTER TABLE tenants ENABLE ROW LEVEL SECURITY",
                "ALTER TABLE users ENABLE ROW LEVEL SECURITY",
                "ALTER TABLE projects ENABLE ROW LEVEL SECURITY",
                "ALTER TABLE documents ENABLE ROW LEVEL SECURITY",
                "ALTER TABLE clauses ENABLE ROW LEVEL SECURITY",
                "ALTER TABLE analyses ENABLE ROW LEVEL SECURITY",
                "ALTER TABLE alerts ENABLE ROW LEVEL SECURITY",
                "ALTER TABLE extractions ENABLE ROW LEVEL SECURITY",
                "ALTER TABLE stakeholders ENABLE ROW LEVEL SECURITY",
                "ALTER TABLE wbs_items ENABLE ROW LEVEL SECURITY",
                "ALTER TABLE bom_items ENABLE ROW LEVEL SECURITY",
                "ALTER TABLE stakeholder_wbs_raci ENABLE ROW LEVEL SECURITY",
            ]
            for stmt in rls_statements:
                await conn.execute(text(stmt))

            await conn.execute(
                text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nonsuperuser') THEN
                        CREATE ROLE nonsuperuser LOGIN PASSWORD 'test';
                    END IF;
                END $$;
            """)
            )
            await conn.execute(text("GRANT USAGE ON SCHEMA public TO nonsuperuser"))
            await conn.execute(
                text(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO nonsuperuser"
                )
            )
            await conn.execute(
                text(
                    "GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO nonsuperuser"
                )
            )
            await conn.execute(
                text(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO nonsuperuser"
                )
            )
            await conn.execute(
                text(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO nonsuperuser"
                )
            )

        print("\nSchema creado exitosamente desde modelos SQLAlchemy")

        # Verificar tablas creadas
        async with engine.connect() as conn:
            result = await conn.execute(
                text("""
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename
            """)
            )
            tables = [row[0] for row in result.fetchall()]
            print(f"\n📋 Tablas creadas ({len(tables)}):")
            for table in tables:
                print(f"  - {table}")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_schema())
