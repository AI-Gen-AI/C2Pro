"""P0-SEC-A: external Data API containment.

Two layers:

* **Static** checks run everywhere with no database. They pin the migration's
  revision chain, its scope boundaries, and parity between the canonical Alembic
  source and the generated Supabase CLI mirror.
* **Catalog** checks run only when ``P0_SEC_A_TEST_DSN`` points at a disposable
  database carrying the Supabase role model. They assert that ``anon`` and
  ``authenticated`` are denied on every protected object while the owner and
  ``service_role`` are unaffected.

The catalog layer is RED before the migration and GREEN after; the recorded run
is in blackboard/SESSION_2026-09-02_p0-sec-supabase-audit.md. Never point these
at production.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

pytestmark = pytest.mark.security

REPO_ROOT = Path(__file__).resolve().parents[4]
MIGRATION = (
    REPO_ROOT
    / "apps/api/alembic/versions/20260902_0001_p0_sec_a_data_api_containment.py"
)
MIRROR = REPO_ROOT / "supabase/migrations/20260902000100_p0_sec_a_data_api_containment.sql"
GENERATOR = REPO_ROOT / "apps/api/scripts/generate_p0_sec_a_mirror.py"

CHECKPOINT_TABLES = (
    "checkpoints",
    "checkpoint_blobs",
    "checkpoint_writes",
    "checkpoint_migrations",
)

RLS_ENABLED_TABLES = (
    "evidence_claims",
    "evidence_extraction_events",
    "category_centroids",
    "project_snapshots_2026_06",
    "project_snapshots_2026_07",
    "project_snapshots_2026_08",
    "project_snapshots_default",
)

PROTECTED_TABLES = CHECKPOINT_TABLES + RLS_ENABLED_TABLES

DSN = os.environ.get("P0_SEC_A_TEST_DSN")
requires_db = pytest.mark.skipif(
    not DSN,
    reason="set P0_SEC_A_TEST_DSN to a disposable database to run catalog checks",
)


def _load_migration() -> types.ModuleType:
    """Import the migration with a stub ``alembic.op`` that records emitted SQL."""
    collected: list[str] = []
    stub = types.ModuleType("alembic")
    stub.op = types.SimpleNamespace(execute=lambda sql: collected.append(str(sql)))
    saved = sys.modules.get("alembic")
    sys.modules["alembic"] = stub
    try:
        spec = importlib.util.spec_from_file_location("p0_sec_a_migration", MIGRATION)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        if saved is not None:
            sys.modules["alembic"] = saved
        else:
            del sys.modules["alembic"]
    module._collected = collected  # type: ignore[attr-defined]
    return module


def _emitted(direction: str) -> str:
    module = _load_migration()
    module._collected.clear()  # type: ignore[attr-defined]
    getattr(module, direction)()
    return "\n".join(module._collected)  # type: ignore[attr-defined]


# --------------------------------------------------------------- static checks


class TestMigrationShape:
    def test_migration_chains_to_production_head(self) -> None:
        module = _load_migration()
        assert module.revision == "20260902_0001"
        # 20260824_0001 is the revision production actually reports in
        # alembic_version. The repository carries other, unmerged heads.
        assert module.down_revision == "20260824_0001"

    def test_upgrade_revokes_tables_and_sequences_from_external_roles(self) -> None:
        sql = _emitted("upgrade")
        assert "REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public" in sql
        assert "REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public" in sql
        assert sql.count("FROM anon, authenticated, PUBLIC") >= 2

    def test_service_role_is_never_revoked(self) -> None:
        """The waitlist route depends on service_role; it must survive intact."""
        for line in _emitted("upgrade").splitlines():
            if "REVOKE" in line.upper():
                assert "service_role" not in line

    def test_upgrade_drops_every_permissive_checkpoint_policy(self) -> None:
        sql = _emitted("upgrade")
        for table in CHECKPOINT_TABLES:
            assert f'DROP POLICY IF EXISTS "{table}_select" ON public.{table}' in sql

    def test_upgrade_enables_rls_on_every_target(self) -> None:
        sql = _emitted("upgrade")
        for table in RLS_ENABLED_TABLES:
            assert f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY" in sql

    def test_upgrade_closes_default_privileges(self) -> None:
        sql = _emitted("upgrade")
        assert "ALTER DEFAULT PRIVILEGES FOR ROLE " in sql
        assert "REVOKE ALL ON TABLES" in sql
        assert "REVOKE ALL ON SEQUENCES" in sql

    def test_default_privilege_change_is_membership_guarded(self) -> None:
        """postgres is not a member of supabase_admin, so an unguarded
        ``ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin`` fails at deploy."""
        assert "pg_has_role(current_user, rec.owner, 'USAGE')" in _emitted("upgrade")

    def test_migration_sql_contains_no_percent_placeholders(self) -> None:
        """A literal '%' is consumed by psycopg2 interpolation under op.execute(),
        so the SQL would behave differently under Alembic than under psql."""
        assert "%" not in _emitted("upgrade")
        assert "%" not in _emitted("downgrade")

    def test_function_privileges_are_out_of_scope(self) -> None:
        """Function EXECUTE grants are P0-SEC-D and need call-path analysis."""
        sql = _emitted("upgrade") + _emitted("downgrade")
        assert "ON FUNCTIONS" not in sql

    def test_fail_open_policies_are_not_touched(self) -> None:
        """Rewriting COALESCE policy bodies is P0-SEC-B, not this migration."""
        sql = _emitted("upgrade")
        assert "COALESCE" not in sql

    def test_no_policy_is_authored_on_snapshot_leaves(self) -> None:
        """Copying the parent's fail-open policy down would reproduce the defect."""
        assert "CREATE POLICY" not in _emitted("upgrade")

    def test_force_rls_is_not_enabled(self) -> None:
        assert "FORCE ROW LEVEL SECURITY" not in _emitted("upgrade")

    def test_downgrade_restores_pre_state(self) -> None:
        sql = _emitted("downgrade")
        assert "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public" in sql
        assert "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public" in sql
        for table in CHECKPOINT_TABLES:
            assert f'CREATE POLICY "{table}_select"' in sql

    def test_downgrade_is_documented_as_insecure(self) -> None:
        module = _load_migration()
        assert "KNOWN-INSECURE" in (module.downgrade.__doc__ or "")


class TestSupabaseMirrorParity:
    def test_mirror_exists(self) -> None:
        assert MIRROR.exists()

    def test_mirror_matches_canonical_alembic_source(self) -> None:
        result = subprocess.run(
            [sys.executable, str(GENERATOR), "--check"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_mirror_is_marked_generated(self) -> None:
        assert "DO NOT EDIT BY HAND" in MIRROR.read_text(encoding="utf-8")


class TestPreStateFixture:
    def test_prestate_fixture_pins_rollback_target(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "p0_sec_a_prestate.sql"
        assert fixture.exists()
        body = fixture.read_text(encoding="utf-8")
        # Rollback must be deterministic, so the fixture pins the exact pre-state.
        assert "USING (true)" in body
        assert "GRANT ALL PRIVILEGES ON ALL TABLES" in body
        # The owner must not be a superuser, or RLS behaviour would be masked.
        assert "NOSUPERUSER BYPASSRLS" in body


# -------------------------------------------------------------- catalog checks


@pytest.fixture(scope="module")
def cursor():  # pragma: no cover - only runs against a disposable database
    psycopg2 = pytest.importorskip("psycopg2")
    conn = psycopg2.connect(DSN)
    conn.autocommit = True
    with conn.cursor() as cur:
        yield cur
    conn.close()


def _denied(cur, role: str, statement: str) -> bool:  # pragma: no cover
    """True when ``role`` cannot run ``statement``. Always resets the role."""
    try:
        cur.execute(f"SET ROLE {role}")
        try:
            cur.execute(statement)
            return False
        except Exception:
            return True
    finally:
        cur.execute("RESET ROLE")


@requires_db
@pytest.mark.parametrize("role", ["anon", "authenticated"])
@pytest.mark.parametrize("table", PROTECTED_TABLES)
def test_external_roles_cannot_select_protected_tables(cursor, role, table):
    assert _denied(cursor, role, f"SELECT count(*) FROM public.{table}")


@requires_db
@pytest.mark.parametrize("role", ["anon", "authenticated"])
@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO public.checkpoints(thread_id,checkpoint_id,checkpoint) "
        "VALUES ('t','c','{}'::jsonb)",
        "UPDATE public.checkpoints SET type='x'",
        "DELETE FROM public.checkpoints",
        "TRUNCATE public.checkpoints",
        "INSERT INTO public.category_centroids(category) VALUES ('poison')",
        "INSERT INTO public.evidence_claims(tenant_id,project_id) "
        "VALUES (gen_random_uuid(),gen_random_uuid())",
    ],
)
def test_external_roles_cannot_mutate_protected_tables(cursor, role, statement):
    assert _denied(cursor, role, statement)


@requires_db
@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_external_roles_cannot_read_document_revisions(cursor, role):
    """The fail-open policy is untouched here; the grant revoke is what denies."""
    assert _denied(cursor, role, "SELECT count(*) FROM public.document_revisions")


@requires_db
def test_no_external_table_grants_remain(cursor):
    cursor.execute(
        "SELECT count(*) FROM information_schema.role_table_grants "
        "WHERE table_schema='public' AND grantee IN ('anon','authenticated')"
    )
    assert cursor.fetchone()[0] == 0


@requires_db
def test_service_role_grants_are_preserved(cursor):
    cursor.execute(
        "SELECT count(*) FROM information_schema.role_table_grants "
        "WHERE table_schema='public' AND grantee='service_role'"
    )
    assert cursor.fetchone()[0] > 0


@requires_db
def test_new_objects_do_not_inherit_external_grants(cursor):
    """The default-ACL recurrence guard: a fresh object must be born closed."""
    cursor.execute("CREATE TABLE public.p0sec_acl_probe (id int)")
    cursor.execute("CREATE SEQUENCE public.p0sec_acl_probe_seq")
    try:
        cursor.execute(
            "SELECT count(*) FROM information_schema.role_table_grants "
            "WHERE table_schema='public' AND table_name='p0sec_acl_probe' "
            "AND grantee IN ('anon','authenticated')"
        )
        assert cursor.fetchone()[0] == 0
        cursor.execute(
            "SELECT count(*) FROM information_schema.role_usage_grants "
            "WHERE object_schema='public' AND object_name='p0sec_acl_probe_seq' "
            "AND grantee IN ('anon','authenticated')"
        )
        assert cursor.fetchone()[0] == 0
    finally:
        cursor.execute("DROP TABLE public.p0sec_acl_probe")
        cursor.execute("DROP SEQUENCE public.p0sec_acl_probe_seq")


@requires_db
def test_checkpoint_rls_remains_enabled_without_policies(cursor):
    cursor.execute(
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' AND c.relrowsecurity "
        "AND c.relname LIKE 'checkpoint' || '%'"
    )
    assert cursor.fetchone()[0] == len(CHECKPOINT_TABLES)
    cursor.execute(
        "SELECT count(*) FROM pg_policies "
        "WHERE schemaname='public' AND tablename LIKE 'checkpoint' || '%'"
    )
    assert cursor.fetchone()[0] == 0


@requires_db
def test_snapshot_leaves_have_rls_and_no_inherited_fail_open_policy(cursor):
    cursor.execute(
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' AND c.relrowsecurity "
        "AND c.relname LIKE 'project_snapshots_' || '%'"
    )
    assert cursor.fetchone()[0] == 4
    cursor.execute(
        "SELECT count(*) FROM pg_policies "
        "WHERE schemaname='public' AND tablename LIKE 'project_snapshots_' || '%'"
    )
    assert cursor.fetchone()[0] == 0
