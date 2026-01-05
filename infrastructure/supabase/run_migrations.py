#!/usr/bin/env python3
"""
C2Pro - Migration Runner

Script para ejecutar migraciones de base de datos de forma segura.
Incluye validación de CTO Gates y rollback en caso de error.

Uso:
    python run_migrations.py --env staging
    python run_migrations.py --env production --confirm
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional

import asyncpg
import structlog
from dotenv import load_dotenv
import os

logger = structlog.get_logger()


class MigrationRunner:
    """Ejecutor de migraciones con validación de seguridad."""

    def __init__(self, database_url: str, migrations_dir: Path):
        self.database_url = database_url
        self.migrations_dir = migrations_dir
        self.conn: Optional[asyncpg.Connection] = None

    async def connect(self) -> None:
        """Conecta a la base de datos."""
        logger.info("connecting_to_database")
        self.conn = await asyncpg.connect(self.database_url)
        logger.info("connected_to_database")

    async def disconnect(self) -> None:
        """Desconecta de la base de datos."""
        if self.conn:
            await self.conn.close()
            logger.info("disconnected_from_database")

    async def get_applied_migrations(self) -> set[str]:
        """Obtiene lista de migraciones ya aplicadas."""
        # Crear tabla de migraciones si no existe
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        rows = await self.conn.fetch("SELECT version FROM schema_migrations ORDER BY version")
        return {row['version'] for row in rows}

    async def get_pending_migrations(self) -> list[Path]:
        """Obtiene lista de migraciones pendientes."""
        applied = await self.get_applied_migrations()

        all_migrations = sorted(self.migrations_dir.glob("*.sql"))
        pending = [
            m for m in all_migrations
            if m.stem not in applied
        ]

        logger.info(
            "migrations_status",
            total=len(all_migrations),
            applied=len(applied),
            pending=len(pending)
        )

        return pending

    async def run_migration(self, migration_path: Path) -> None:
        """Ejecuta una migración individual."""
        logger.info("running_migration", migration=migration_path.name)

        # Leer contenido de migración
        sql = migration_path.read_text(encoding='utf-8')

        # Ejecutar en transacción
        async with self.conn.transaction():
            try:
                await self.conn.execute(sql)

                # Registrar migración aplicada
                await self.conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES ($1)",
                    migration_path.stem
                )

                logger.info("migration_completed", migration=migration_path.name)

            except Exception as e:
                logger.error(
                    "migration_failed",
                    migration=migration_path.name,
                    error=str(e)
                )
                raise

    async def validate_cto_gates(self) -> dict[str, bool]:
        """
        Valida CTO Gates después de ejecutar migraciones.

        Returns:
            Dict con resultado de cada gate
        """
        logger.info("validating_cto_gates")

        gates = {}

        # GATE 1: Multi-tenant Isolation (RLS en 18 tablas)
        rls_count = await self.conn.fetchval("""
            SELECT COUNT(*)
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relrowsecurity = true
            AND n.nspname = 'public'
        """)
        gates['gate_1_rls'] = rls_count >= 18
        logger.info("gate_1_multi_tenant_rls", count=rls_count, passed=gates['gate_1_rls'])

        # GATE 2: Identity Model (UNIQUE tenant_id, email)
        unique_constraint_exists = await self.conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'users_tenant_email_unique'
            )
        """)
        gates['gate_2_identity'] = unique_constraint_exists
        logger.info("gate_2_identity_model", passed=gates['gate_2_identity'])

        # GATE 4: Legal Traceability (tabla clauses existe)
        clauses_table_exists = await self.conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM pg_tables
                WHERE tablename = 'clauses'
            )
        """)
        gates['gate_4_traceability'] = clauses_table_exists
        logger.info("gate_4_legal_traceability", passed=gates['gate_4_traceability'])

        # Verificar FKs clause_id
        clause_fks = await self.conn.fetch("""
            SELECT
                tc.table_name,
                kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND kcu.column_name LIKE '%clause_id%'
        """)
        gates['gate_4_clause_fks'] = len(clause_fks) >= 4  # stakeholders, wbs, bom, alerts
        logger.info(
            "gate_4_clause_foreign_keys",
            count=len(clause_fks),
            passed=gates['gate_4_clause_fks']
        )

        # Verificar vistas MCP existen
        mcp_views = await self.conn.fetch("""
            SELECT viewname FROM pg_views
            WHERE schemaname = 'public'
            AND viewname LIKE 'v_project_%'
        """)
        gates['gate_3_mcp_views'] = len(mcp_views) >= 4
        logger.info("gate_3_mcp_views", count=len(mcp_views), passed=gates['gate_3_mcp_views'])

        # Resumen
        all_passed = all(gates.values())
        logger.info(
            "cto_gates_summary",
            total=len(gates),
            passed=sum(gates.values()),
            all_passed=all_passed,
            gates=gates
        )

        return gates

    async def run_all_pending(self) -> None:
        """Ejecuta todas las migraciones pendientes."""
        pending = await self.get_pending_migrations()

        if not pending:
            logger.info("no_pending_migrations")
            return

        for migration in pending:
            await self.run_migration(migration)

        # Validar CTO Gates después de migrar
        gates = await self.validate_cto_gates()

        if not all(gates.values()):
            logger.warning("cto_gates_validation_failed", gates=gates)
            print("\n⚠️  ATENCIÓN: Algunas CTO Gates no pasaron la validación")
            print("Revisa los logs arriba para detalles")
            sys.exit(1)
        else:
            logger.info("cto_gates_validation_passed")
            print("\n✅ Todas las CTO Gates pasaron la validación")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="C2Pro Migration Runner")
    parser.add_argument(
        "--env",
        choices=["local", "staging", "production"],
        default="local",
        help="Environment to run migrations"
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required for production migrations"
    )
    args = parser.parse_args()

    # Cargar variables de entorno
    env_file = f".env.{args.env}" if args.env != "local" else ".env"
    load_dotenv(env_file)

    # Validar confirmación para producción
    if args.env == "production" and not args.confirm:
        print("❌ ERROR: Se requiere --confirm para ejecutar migraciones en producción")
        sys.exit(1)

    # Obtener database URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ ERROR: DATABASE_URL no está configurado")
        sys.exit(1)

    # Convertir a asyncpg format si es necesario
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql://", 1)

    # Configurar logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer()
        ]
    )

    # Ejecutar migraciones
    migrations_dir = Path(__file__).parent / "migrations"
    runner = MigrationRunner(database_url, migrations_dir)

    try:
        await runner.connect()

        print(f"\n🚀 Ejecutando migraciones en entorno: {args.env}")
        print(f"📁 Directorio de migraciones: {migrations_dir}")
        print("")

        await runner.run_all_pending()

        print("\n✅ Migraciones completadas exitosamente")

    except Exception as e:
        logger.error("migration_error", error=str(e))
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)

    finally:
        await runner.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
