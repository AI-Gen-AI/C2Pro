"""C1 (Option-C runtime RLS completeness): tenant-GUC-name fix migration tests.

CLASSIFICATION: functional-correctness fix, not merely defense-in-depth.
dlq_failed_tasks, wbs_nodes, notification_configs, and disclaimer_acceptances
carry Alembic-created RLS policies referencing a GUC
(``app.current_tenant_id``) the application never sets -- only
``app.current_tenant`` is ever set, in ``src/core/database.py``. Under real
RLS enforcement (no table-ownership bypass, no BYPASSRLS) these four tables
are permanently deny-all for every tenant, correct or not. Today this is
invisible because the shared runtime role owns every table.

* **Static** checks (``TestMigrationShape``) require no database and always
  run.
* The full RED (deny-all-for-everyone) -> GREEN (correct-tenant works,
  wrong-tenant/absent/empty GUC denied) -> RED (downgrade) -> GREEN
  (re-apply) cycle, including wbs_nodes' new INSERT/UPDATE/DELETE write
  paths, lives in the standalone disposable-database gate
  ``apps/api/scripts/c1_gate.py`` (same pattern as
  ``p0_sec_b_gate.py``/``p0_sec_d_gate.py``). This file is a lighter
  pytest-native smoke test over the same migration.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "apps/api/scripts"))

import c1_common as _common  # noqa: E402
from security_gate_common import exec_sql, is_loopback_dsn  # noqa: E402

pytestmark = pytest.mark.security

_RAW_DSN = os.environ.get("P0_SEC_ADMIN_DSN")
DSN = _RAW_DSN if _RAW_DSN and is_loopback_dsn(_RAW_DSN) else None
requires_db = pytest.mark.skipif(
    not DSN,
    reason="set P0_SEC_ADMIN_DSN to a loopback admin DSN to run catalog checks",
)

_FIXED_TABLES = (
    "dlq_failed_tasks",
    "wbs_nodes",
    "notification_configs",
    "disclaimer_acceptances",
)


# ═══════════════════════════════════════════════════════════ static checks


class TestMigrationShape:
    def test_fix_migration_exists(self) -> None:
        assert _common.MIGRATION_PATH.exists(), f"{_common.MIGRATION_PATH} is missing"

    def test_upgrade_never_references_broken_guc_name(self) -> None:
        """The fix must not reintroduce app.current_tenant_id anywhere."""
        sql = _common.emitted_sql("upgrade")
        assert "app.current_tenant_id" not in sql
        assert sql.count("app.current_tenant'") >= len(_FIXED_TABLES)

    def test_upgrade_uses_canonical_nullif_predicate(self) -> None:
        sql = _common.emitted_sql("upgrade")
        canonical = "NULLIF(current_setting('app.current_tenant', true), '')::uuid"
        assert canonical in sql

    def test_upgrade_touches_exactly_the_four_confirmed_tables(self) -> None:
        sql = _common.emitted_sql("upgrade")
        for table in _FIXED_TABLES:
            assert f"ON {table} " in sql or sql.count(table) >= 1, (
                f"upgrade() does not appear to touch {table}"
            )
        # Tables C1 explicitly decided need zero c2pro_app grant/policy work
        # (dead code / offline-script-only / already-correct) must not be
        # touched by this migration.
        for excluded in (
            "evidence_claims",
            "evidence_extraction_events",
            "category_centroids",
            "review_items",
            "checkpoints",
            "checkpoint_blobs",
            "checkpoint_writes",
            "checkpoint_migrations",
        ):
            assert excluded not in sql, (
                f"upgrade() unexpectedly touches {excluded}, which C1 excluded"
            )

    def test_wbs_nodes_gets_all_four_commands(self) -> None:
        """wbs_nodes is the one table with a confirmed live DELETE caller."""
        sql = _common.emitted_sql("upgrade")
        for cmd in ("FOR SELECT", "FOR INSERT", "FOR UPDATE", "FOR DELETE"):
            assert f"wbs_nodes_tenant_isolation_{cmd.split()[-1].lower()} ON wbs_nodes {cmd}" in sql

    def test_dlq_and_notification_configs_get_no_delete_policy(self) -> None:
        """No live DELETE caller was found for either table -- narrowest contract."""
        sql = _common.emitted_sql("upgrade")
        assert "dlq_tenant_isolation_delete" not in sql
        assert "notification_configs_tenant_isolation_delete" not in sql

    def test_disclaimer_acceptances_keeps_select_insert_only(self) -> None:
        sql = _common.emitted_sql("upgrade")
        assert "disclaimer_tenant_isolation_select" in sql
        assert "disclaimer_tenant_isolation_insert" in sql
        assert "disclaimer_tenant_isolation_update" not in sql
        assert "disclaimer_tenant_isolation_delete" not in sql

    def test_downgrade_restores_exact_prefix_predicate_bytes(self) -> None:
        """Downgrade must reproduce the original bug precisely, not approximate it."""
        sql = _common.emitted_sql("downgrade")
        assert "current_setting('app.current_tenant_id', TRUE)::uuid" in sql
        assert "current_setting('app.current_tenant_id')::uuid" in sql  # notification_configs

    def test_no_alembic_migration_grants_to_c2pro_app_or_creates_a_role(self) -> None:
        """C1 fixes policies only -- role creation/GRANTs are C3 cutover work."""
        sql = _common.emitted_sql("upgrade") + _common.emitted_sql("downgrade")
        assert "c2pro_app" not in sql
        assert "CREATE ROLE" not in sql.upper()
        assert "GRANT " not in sql.upper()


# ═══════════════════════════════════════════════════════ catalog checks


@requires_db
class TestCatalogGate:
    """Lightweight integration smoke test; the exhaustive RED/GREEN/write-path

    proof lives in apps/api/scripts/c1_gate.py.
    """

    def test_upgrade_applies_cleanly_to_prestate_fixture(self, disposable_db: str) -> None:
        fixture = REPO_ROOT / "apps/api/tests/security/fixtures/c1_prestate.sql"
        exec_sql(disposable_db, path=fixture)
        exec_sql(disposable_db, sql=_common.emitted_sql("upgrade"))

        exec_sql(disposable_db, sql="SET ROLE c2pro_sec_rls_test")
        exec_sql(disposable_db, sql="RESET ROLE")


@pytest.fixture
def disposable_db() -> str:
    """Create and drop a scratch database on the loopback admin DSN."""
    admin = DSN
    assert admin is not None  # guarded by requires_db
    db_name = "c1_pytest_scratch"
    target = admin.rsplit("/", 1)[0] + "/" + db_name

    exec_sql(admin, sql=f'DROP DATABASE IF EXISTS "{db_name}"')
    exec_sql(admin, sql=f'CREATE DATABASE "{db_name}"')
    try:
        yield target
    finally:
        exec_sql(admin, sql=f'DROP DATABASE IF EXISTS "{db_name}"')
