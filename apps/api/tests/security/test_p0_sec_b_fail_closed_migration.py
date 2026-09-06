"""P0-SEC-B: fail-closed COALESCE → NULLIF RLS policy migration.

Three layers:

* **Static** checks run everywhere with no database. They pin the migration's
  revision chain, assert no COALESCE appears in the upgrade output, verify the
  downgrade is documented KNOWN-INSECURE, and check parity between the
  canonical Alembic source and the generated Supabase CLI mirror.

* **Pre-state fixture** checks verify the test fixture file is structurally
  correct (contains COALESCE, the non-BYPASSRLS role is present, etc.).

* **Catalog** checks run only when ``P0_SEC_B_TEST_DSN`` points at a loopback
  admin DSN.  They build a disposable database from the pre-state fixture,
  assert TRUE RED (GUC-absent / GUC-empty sees all rows before migration),
  apply the migration, assert GREEN (GUC-absent / GUC-empty sees no rows),
  assert behavioral invariants (wrong/correct tenant), verify the precondition
  aborts on bad data, and confirm P0-SEC-A tables are unaffected.

Never point these at production.

TRUE_RED_TESTS_FAILED_BEFORE  — verified in catalog phase 'pre-state'.
INVARIANT_TESTS_PASSED_BEFORE — verified in catalog phase 'pre-state invariants'.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest

pytestmark = pytest.mark.security

REPO_ROOT = Path(__file__).resolve().parents[4]
MIGRATION = (
    REPO_ROOT
    / "apps/api/alembic/versions/20260905_0001_p0_sec_b_fail_closed_policies.py"
)
MIRROR = (
    REPO_ROOT
    / "supabase/migrations/20260905000100_p0_sec_b_fail_closed_policies.sql"
)
GENERATOR = REPO_ROOT / "apps/api/scripts/generate_p0_sec_b_mirror.py"
FIXTURE = REPO_ROOT / "apps/api/tests/security/fixtures/p0_sec_b_prestate.sql"
SUPABASE_POLICY_DELTA = REPO_ROOT / "apps/api/tests/security/fixtures/p0_sec_b_supabase_policy_delta.sql"

sys.path.insert(0, str(REPO_ROOT / "apps/api/scripts"))
from p0_sec_b_common import emitted_sql as _emitted_sql  # noqa: E402
from p0_sec_b_common import load_migration as _load_migration  # noqa: E402

COALESCE_EXPR = "COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id)"
NULLIF_EXPR = "NULLIF(current_setting('app.current_tenant', true), '')::uuid"

COALESCE_TABLES = (
    "project_states",
    "project_state_entities",
    "document_revisions",
    "project_events",
    "project_snapshots",
    "document_artifacts",
)

COALESCE_POLICIES = (
    ("project_states",         "project_states_select"),
    ("project_states",         "project_states_insert"),
    ("project_states",         "project_states_update"),
    ("project_states",         "project_states_delete"),
    ("project_state_entities", "pse_select"),
    ("project_state_entities", "pse_insert"),
    ("project_state_entities", "pse_update"),
    ("project_state_entities", "pse_delete"),
    ("document_revisions",     "docrev_select"),
    ("document_revisions",     "docrev_insert"),
    ("document_revisions",     "docrev_update"),
    ("document_revisions",     "docrev_delete"),
    ("project_events",         "project_events_select"),
    ("project_events",         "project_events_insert"),
    ("project_events",         "project_events_update"),
    ("project_events",         "project_events_delete"),
    ("project_snapshots",      "project_snapshots_select"),
    ("project_snapshots",      "project_snapshots_insert"),
    ("project_snapshots",      "project_snapshots_update"),
    ("project_snapshots",      "project_snapshots_delete"),
    ("document_artifacts",     "document_artifacts_select"),
    ("document_artifacts",     "document_artifacts_insert"),
    ("document_artifacts",     "document_artifacts_update"),
    ("document_artifacts",     "document_artifacts_delete"),
)

EXCESS_POLICIES = (
    ("analyses",          "tenant_isolation_analyses"),
    ("alerts",            "tenant_isolation_alerts"),
    ("coherence_results", "tenant_isolation_coherence_results"),
    ("clause_embeddings", "tenant_isolation_clause_embeddings"),
    ("clause_embeddings", "clause_embeddings_tenant_isolation"),
)

# Supabase CLI historical policy names created by the June 2026 migrations
# (20260613000100 and 20260614000100).  These use NULLIF expressions (already
# fail-closed) but differ in name from the Alembic-canonical short names.
# P0-SEC-B upgrade must DROP them so both migration paths converge to exactly
# 4 canonical policies per table with no catalog pollution.
# Each entry: (table, select_name, insert_name, update_name, delete_name)
SUPABASE_LEGACY_POLICIES: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "project_states",
        "project_states_tenant_isolation_select",
        "project_states_tenant_isolation_insert",
        "project_states_tenant_isolation_update",
        "project_states_tenant_isolation_delete",
    ),
    (
        "project_state_entities",
        "project_state_entities_tenant_isolation_select",
        "project_state_entities_tenant_isolation_insert",
        "project_state_entities_tenant_isolation_update",
        "project_state_entities_tenant_isolation_delete",
    ),
    (
        "document_revisions",
        "document_revisions_tenant_isolation_select",
        "document_revisions_tenant_isolation_insert",
        "document_revisions_tenant_isolation_update",
        "document_revisions_tenant_isolation_delete",
    ),
    (
        "project_events",
        "project_events_tenant_isolation_select",
        "project_events_tenant_isolation_insert",
        "project_events_tenant_isolation_update",
        "project_events_tenant_isolation_delete",
    ),
    (
        "project_snapshots",
        "project_snapshots_tenant_isolation_select",
        "project_snapshots_tenant_isolation_insert",
        "project_snapshots_tenant_isolation_update",
        "project_snapshots_tenant_isolation_delete",
    ),
    (
        "document_artifacts",
        "document_artifacts_tenant_isolation_select",
        "document_artifacts_tenant_isolation_insert",
        "document_artifacts_tenant_isolation_update",
        "document_artifacts_tenant_isolation_delete",
    ),
)

TENANT_A = "aaaaaaaa-aaaa-aaaa-aaaa-000000000001"
TENANT_B = "bbbbbbbb-bbbb-bbbb-bbbb-000000000002"
PROJECT_A = "cccccccc-cccc-cccc-cccc-000000000001"

DSN = os.environ.get("P0_SEC_B_TEST_DSN")
requires_db = pytest.mark.skipif(
    not DSN,
    reason="set P0_SEC_B_TEST_DSN to a loopback admin DSN to run catalog checks",
)


# ═══════════════════════════════════════════════════════════ static checks


class TestMigrationShape:
    def test_revision_chain(self) -> None:
        m = _load_migration()
        assert m.revision == "20260905_0001"
        assert m.down_revision == "20260902_0001"

    def test_upgrade_contains_no_coalesce_in_policies(self) -> None:
        """After migration every policy must use NULLIF, not COALESCE."""
        sql = _emitted_sql("upgrade")
        # Policies are CREATE POLICY statements; COALESCE must not appear in them.
        for line in sql.splitlines():
            if "CREATE POLICY" in line:
                assert "COALESCE" not in line, f"COALESCE found in policy: {line}"

    def test_upgrade_contains_all_24_policy_drops(self) -> None:
        sql = _emitted_sql("upgrade")
        for table, policy in COALESCE_POLICIES:
            assert f"DROP POLICY IF EXISTS {policy} ON {table}" in sql, (
                f"upgrade missing DROP for {policy} ON {table}"
            )

    def test_upgrade_contains_all_24_nullif_policy_creates(self) -> None:
        sql = _emitted_sql("upgrade")
        for table, policy in COALESCE_POLICIES:
            assert f"CREATE POLICY {policy} ON {table}" in sql, (
                f"upgrade missing CREATE for {policy} ON {table}"
            )

    def test_upgrade_drops_all_5_excess_policies(self) -> None:
        sql = _emitted_sql("upgrade")
        for table, policy in EXCESS_POLICIES:
            assert f"DROP POLICY IF EXISTS {policy} ON {table}" in sql, (
                f"upgrade missing DROP for excess policy {policy} ON {table}"
            )

    def test_upgrade_does_not_create_excess_policies(self) -> None:
        sql = _emitted_sql("upgrade")
        for _table, policy in EXCESS_POLICIES:
            assert f"CREATE POLICY {policy}" not in sql, (
                f"upgrade must not recreate excess policy {policy}"
            )

    def test_upgrade_has_lock_timeout(self) -> None:
        assert "lock_timeout" in _emitted_sql("upgrade")

    def test_upgrade_has_precondition_block(self) -> None:
        sql = _emitted_sql("upgrade")
        assert "P0-SEC-B PRECONDITION FAILED" in sql

    def test_precondition_skips_if_projects_absent(self) -> None:
        sql = _emitted_sql("upgrade")
        assert "information_schema.tables" in sql
        assert "table_name = 'projects'" in sql or "table_name='projects'" in sql

    def test_upgrade_sql_has_no_bare_psycopg2_placeholders(self) -> None:
        """The precondition uses quote_ident() + string concatenation (no % signs).
        The policy USING/WITH CHECK expressions contain no % either.
        Verify no bare '%' remain after stripping any '%%' escape pairs."""
        sql = _emitted_sql("upgrade")
        after_strip = sql.replace("%%", "")
        assert "%" not in after_strip, (
            "Bare '%' found in upgrade SQL after removing '%%' pairs — "
            "psycopg2 would consume it as a placeholder"
        )

    def test_downgrade_sql_has_no_bare_psycopg2_placeholders(self) -> None:
        sql = _emitted_sql("downgrade")
        after_strip = sql.replace("%%", "")
        assert "%" not in after_strip, (
            "Bare '%' found in downgrade SQL after removing '%%' pairs"
        )

    def test_downgrade_restores_coalesce_policies(self) -> None:
        sql = _emitted_sql("downgrade")
        assert "COALESCE" in sql

    def test_downgrade_restores_excess_policies(self) -> None:
        sql = _emitted_sql("downgrade")
        for _table, policy in EXCESS_POLICIES:
            assert f"CREATE POLICY {policy}" in sql

    def test_downgrade_is_documented_as_known_insecure(self) -> None:
        m = _load_migration()
        assert "KNOWN-INSECURE" in (m.downgrade.__doc__ or "")

    def test_24_policies_across_6_tables(self) -> None:
        assert len(COALESCE_POLICIES) == 24
        tables = {t for t, _ in COALESCE_POLICIES}
        assert len(tables) == 6

    def test_5_excess_policies_across_4_tables(self) -> None:
        assert len(EXCESS_POLICIES) == 5
        tables = {t for t, _ in EXCESS_POLICIES}
        assert len(tables) == 4

    def test_migration_does_not_touch_p0_sec_a_tables(self) -> None:
        """P0-SEC-A scope (checkpoint/evidence/snapshot-leaf RLS) must be untouched."""
        upgrade = _emitted_sql("upgrade")
        downgrade = _emitted_sql("downgrade")
        p0_sec_a_tables = (
            "checkpoints",
            "checkpoint_blobs",
            "checkpoint_writes",
            "checkpoint_migrations",
            "evidence_claims",
            "evidence_extraction_events",
            "category_centroids",
        )
        for table in p0_sec_a_tables:
            for sql in (upgrade, downgrade):
                assert f"ON {table}" not in sql or "DROP POLICY IF EXISTS" not in sql, (
                    f"migration unexpectedly alters P0-SEC-A table {table}"
                )

    def test_precondition_covers_all_coalesce_tables(self) -> None:
        """FINDING 1 RED: _PRECONDITION_TABLES must include every COALESCE table.

        Before fix: only 4 excess-policy tables are listed ('analyses', 'alerts',
        'coherence_results', 'clause_embeddings').  The 6 COALESCE tables all
        carry project_id NOT NULL, so a tenant/project mismatch or orphaned
        project_id in them is not verified before the migration executes.

        RED: each COALESCE_TABLES member is absent from _PRECONDITION_TABLES →
        the assertion fails on the first missing table.
        GREEN: _PRECONDITION_TABLES expanded to all 10 tables.
        """
        m = _load_migration()
        for table in COALESCE_TABLES:
            assert table in m._PRECONDITION_TABLES, (
                f"FINDING 1: {table} not in _PRECONDITION_TABLES — "
                "tenant/project mismatch or orphaned project_id in this "
                "COALESCE table is not checked before migration"
            )

    def test_upgrade_drops_supabase_legacy_policy_names(self) -> None:
        """FINDING 2 RED: upgrade must DROP Supabase-historical *_tenant_isolation_* names.

        The June 2026 Supabase CLI path (20260613000100, 20260614000100) created
        the 6 COALESCE tables with NULLIF policies named *_tenant_isolation_*.
        After P0-SEC-B upgrade on that path, each table would have 2 PERMISSIVE
        policies per operation (both NULLIF fail-closed) — catalog pollution even
        though there is no security regression.

        The fix adds IF EXISTS DROPs for all 24 legacy names so both paths converge
        to exactly 4 canonical policies per table.

        RED: upgrade SQL has no DROP for any *_tenant_isolation_* name.
        GREEN: all 24 legacy DROPs present.
        """
        sql = _emitted_sql("upgrade")
        for table, sel, ins, upd, dlt in SUPABASE_LEGACY_POLICIES:
            for name in (sel, ins, upd, dlt):
                assert f"DROP POLICY IF EXISTS {name} ON {table}" in sql, (
                    f"FINDING 2: upgrade missing DROP for Supabase-historical "
                    f"policy {name} ON {table} — migration paths do not converge"
                )


# ══════════════════════════════════════════════════════ mirror parity


class TestSupabaseMirrorParity:
    def test_mirror_exists(self) -> None:
        assert MIRROR.exists(), f"Supabase mirror not found: {MIRROR}"

    def test_mirror_matches_canonical_alembic_source(self) -> None:
        result = subprocess.run(
            [sys.executable, str(GENERATOR), "--check"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_mirror_is_marked_generated(self) -> None:
        assert "DO NOT EDIT BY HAND" in MIRROR.read_text(encoding="utf-8")

    def test_mirror_contains_no_coalesce_in_policies(self) -> None:
        sql = MIRROR.read_text(encoding="utf-8")
        for line in sql.splitlines():
            if "CREATE POLICY" in line:
                assert "COALESCE" not in line


# ═══════════════════════════════════════════════════ prestate fixture


class TestPreStateFixture:
    def test_fixture_exists(self) -> None:
        assert FIXTURE.exists()

    def test_fixture_contains_coalesce_policies(self) -> None:
        body = FIXTURE.read_text(encoding="utf-8")
        assert "COALESCE" in body

    def test_fixture_has_nobypassrls_test_role(self) -> None:
        body = FIXTURE.read_text(encoding="utf-8")
        assert "c2pro_sec_rls_test" in body
        assert "NOBYPASSRLS" in body

    def test_fixture_has_nosuperuser_test_role(self) -> None:
        body = FIXTURE.read_text(encoding="utf-8")
        assert "NOSUPERUSER" in body

    def test_fixture_has_seed_rows_for_two_tenants(self) -> None:
        body = FIXTURE.read_text(encoding="utf-8")
        assert TENANT_A in body
        assert TENANT_B in body

    def test_fixture_has_projects_stub_table(self) -> None:
        body = FIXTURE.read_text(encoding="utf-8")
        assert "CREATE TABLE" in body
        assert "projects" in body

    def test_fixture_covers_all_6_coalesce_tables(self) -> None:
        body = FIXTURE.read_text(encoding="utf-8")
        for table in COALESCE_TABLES:
            assert table in body, f"prestate fixture missing table {table}"


# ═══════════════════════════════════════════════════════ catalog checks
#
# These tests require P0_SEC_B_TEST_DSN to point at a loopback admin DSN.
# Each test class uses module-scoped fixtures that create and drop independent
# disposable databases, so the tests are fully self-contained.


def _db_conn(dsn: str):
    """Return a psycopg(2) connection with autocommit=True."""
    try:
        import psycopg
        conn = psycopg.connect(dsn, autocommit=True)
        return conn
    except ImportError:
        import psycopg2
        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        return conn


def _exec_sql(dsn: str, sql: str) -> None:
    conn = _db_conn(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
    finally:
        conn.close()


def _count_as_role(dsn: str, table: str, *, tenant_guc: str | None) -> int:
    """Count rows visible to c2pro_sec_rls_test under the given GUC."""
    conn = _db_conn(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute("RESET app.current_tenant")
            if tenant_guc is not None:
                # SET ... = %s is rejected by psycopg3 (PostgreSQL rejects bind
                # parameters in SET commands).  set_config() accepts %s cleanly.
                cur.execute(
                    "SELECT set_config('app.current_tenant', %s, false)",
                    (tenant_guc,),
                )
            cur.execute("SET ROLE c2pro_sec_rls_test")
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table}")  # nosec B608
                row = cur.fetchone()
                return int(row[0]) if row else 0
            finally:
                cur.execute("RESET ROLE")
                cur.execute("RESET app.current_tenant")
    finally:
        conn.close()


def _make_db_dsn(admin_dsn: str, db_name: str) -> str:
    return admin_dsn.rsplit("/", 1)[0] + "/" + db_name


@contextmanager
def _disposable_db(admin_dsn: str, db_name: str, fixture_path: Path):
    """Context manager: create a disposable DB, load fixture, yield DSN, drop."""
    db_dsn = _make_db_dsn(admin_dsn, db_name)
    _exec_sql(admin_dsn, f'DROP DATABASE IF EXISTS "{db_name}"')
    _exec_sql(admin_dsn, f'CREATE DATABASE "{db_name}"')
    try:
        _exec_sql(db_dsn, fixture_path.read_text(encoding="utf-8"))
        yield db_dsn
    finally:
        _exec_sql(admin_dsn, f'DROP DATABASE IF EXISTS "{db_name}"')


@pytest.fixture(scope="module")
def prestate_dsn():
    """Module-scoped: disposable DB in COALESCE pre-state."""
    if not DSN:
        yield None
        return
    db_name = f"p0_sec_b_test_prestate_{uuid.uuid4().hex[:8]}"
    with _disposable_db(DSN, db_name, FIXTURE) as dsn:
        yield dsn


@pytest.fixture(scope="module")
def migrated_dsn(prestate_dsn):
    """Module-scoped: same DB with upgrade applied."""
    if prestate_dsn is None:
        yield None
        return
    _exec_sql(prestate_dsn, _emitted_sql("upgrade"))
    yield prestate_dsn


@pytest.fixture(scope="module")
def supabase_prestate_dsn():
    """Module-scoped: disposable DB in Supabase-historical pre-state (PATH B).

    Builds the database by composing the shared Alembic base fixture
    (p0_sec_b_prestate.sql) with the Supabase-historical policy delta
    (p0_sec_b_supabase_policy_delta.sql).  The delta drops the 24 COALESCE
    short-named policies and replaces them with the 24 NULLIF
    *_tenant_isolation_* policies that the June 2026 Supabase CLI migrations
    emitted.  The final state is semantically identical to the former
    p0_sec_b_supabase_prestate.sql but without duplicating the shared DDL.
    """
    if not DSN:
        yield None
        return
    db_name = f"p0_sec_b_test_supa_pre_{uuid.uuid4().hex[:8]}"
    with _disposable_db(DSN, db_name, FIXTURE) as dsn:
        _exec_sql(dsn, SUPABASE_POLICY_DELTA.read_text(encoding="utf-8"))
        yield dsn


@pytest.fixture(scope="module")
def supabase_migrated_dsn(supabase_prestate_dsn):
    """Module-scoped: Supabase-historical DB with checked-in mirror SQL applied (PATH B).

    Deliberately applies MIRROR.read_text() (the checked-in Supabase mirror SQL),
    NOT _emitted_sql("upgrade"), to prove PATH B converges via the file that
    Supabase preview bot actually applies.
    """
    if supabase_prestate_dsn is None:
        yield None
        return
    _exec_sql(supabase_prestate_dsn, MIRROR.read_text(encoding="utf-8"))
    yield supabase_prestate_dsn


# ─────────────────────────────────────────── TRUE RED catalog (pre-migration)


@requires_db
class TestTrueRedCatalog:
    """TRUE_RED_TESTS_FAILED_BEFORE: GUC-absent and GUC='' must expose all rows."""

    @pytest.mark.parametrize("table", COALESCE_TABLES)
    def test_guc_absent_sees_all_rows_before_migration(self, prestate_dsn, table) -> None:
        count = _count_as_role(prestate_dsn, table, tenant_guc=None)
        assert count > 0, (
            f"RED FAILED: {table} returned 0 rows with no GUC "
            f"— COALESCE fail-open not reproducing in prestate"
        )

    @pytest.mark.parametrize("table", COALESCE_TABLES)
    def test_empty_guc_sees_all_rows_before_migration(self, prestate_dsn, table) -> None:
        count = _count_as_role(prestate_dsn, table, tenant_guc="")
        assert count > 0, (
            f"RED FAILED: {table} returned 0 rows with empty GUC "
            f"— COALESCE fail-open not reproducing in prestate"
        )


# ─────────────────────────────────── BEHAVIORAL INVARIANTS catalog (pre-migration)


@requires_db
class TestInvariantsBefore:
    """INVARIANT_TESTS_PASSED_BEFORE: wrong/correct tenant isolation holds pre-migration."""

    @pytest.mark.parametrize("table", COALESCE_TABLES)
    def test_wrong_tenant_sees_only_own_rows_before_migration(self, prestate_dsn, table) -> None:
        count = _count_as_role(prestate_dsn, table, tenant_guc=TENANT_B)
        assert count == 1, (
            f"INVARIANT FAILED pre-migration: {table}: TENANT_B GUC returned "
            f"{count} rows, expected 1 (TENANT_B's own row)"
        )

    @pytest.mark.parametrize("table", COALESCE_TABLES)
    def test_correct_tenant_sees_own_rows_before_migration(self, prestate_dsn, table) -> None:
        count = _count_as_role(prestate_dsn, table, tenant_guc=TENANT_A)
        assert count == 1, (
            f"INVARIANT FAILED pre-migration: {table}: TENANT_A GUC returned "
            f"{count} rows, expected 1 (TENANT_A's own row)"
        )


# ─────────────────────────────────────────── GREEN catalog (post-migration)


@requires_db
class TestGreenCatalog:
    """GUC-absent and GUC='' must return zero rows after migration."""

    @pytest.mark.parametrize("table", COALESCE_TABLES)
    def test_guc_absent_sees_no_rows_after_migration(self, migrated_dsn, table) -> None:
        count = _count_as_role(migrated_dsn, table, tenant_guc=None)
        assert count == 0, (
            f"GREEN FAILED: {table} returned {count} rows with no GUC after migration "
            f"— NULLIF fail-closed not applied?"
        )

    @pytest.mark.parametrize("table", COALESCE_TABLES)
    def test_empty_guc_sees_no_rows_after_migration(self, migrated_dsn, table) -> None:
        count = _count_as_role(migrated_dsn, table, tenant_guc="")
        assert count == 0, (
            f"GREEN FAILED: {table} returned {count} rows with empty GUC after migration "
            f"— NULLIF fail-closed not applied?"
        )


# ─────────────────────────────────── BEHAVIORAL INVARIANTS catalog (post-migration)


@requires_db
class TestInvariantsAfter:
    """Wrong/correct tenant isolation must hold after migration."""

    @pytest.mark.parametrize("table", COALESCE_TABLES)
    def test_wrong_tenant_sees_only_own_rows_after_migration(self, migrated_dsn, table) -> None:
        count = _count_as_role(migrated_dsn, table, tenant_guc=TENANT_B)
        assert count == 1, (
            f"INVARIANT FAILED post-migration: {table}: TENANT_B GUC returned "
            f"{count} rows, expected 1"
        )

    @pytest.mark.parametrize("table", COALESCE_TABLES)
    def test_correct_tenant_sees_own_rows_after_migration(self, migrated_dsn, table) -> None:
        count = _count_as_role(migrated_dsn, table, tenant_guc=TENANT_A)
        assert count == 1, (
            f"INVARIANT FAILED post-migration: {table}: TENANT_A GUC returned "
            f"{count} rows, expected 1"
        )


# ──────────────────────────────────────────── PRECONDITION ABORT catalog


@requires_db
class TestPreconditionAbort:
    """Upgrade must abort when tenant_id/projects.tenant_id disagree."""

    def test_precondition_aborts_on_mismatched_row(self) -> None:
        if not DSN:
            pytest.skip("requires P0_SEC_B_TEST_DSN")

        db_name = f"p0_sec_b_test_abort_{uuid.uuid4().hex[:8]}"
        with _disposable_db(DSN, db_name, FIXTURE) as db_dsn:
            bad_id = str(uuid.uuid4())
            # Insert analyses row where tenant_id disagrees with PROJECT_A's tenant.
            _exec_sql(
                db_dsn,
                f"INSERT INTO analyses (id, project_id, tenant_id) VALUES "
                f"('{bad_id}'::uuid, '{PROJECT_A}'::uuid, '{TENANT_B}'::uuid)",
            )

            # The upgrade must raise the precondition exception.
            got_expected = False
            try:
                _exec_sql(db_dsn, _emitted_sql("upgrade"))
            except Exception as exc:
                if "P0-SEC-B PRECONDITION FAILED" in str(exc):
                    got_expected = True
                else:
                    raise

            assert got_expected, (
                "upgrade did not raise P0-SEC-B PRECONDITION FAILED on mismatched data"
            )

            # Verify the COALESCE policies are still in place (upgrade rolled back).
            conn = _db_conn(db_dsn)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT COUNT(*) FROM pg_policies "
                        "WHERE schemaname='public' AND tablename='project_states' "
                        "AND policyname='project_states_select' "
                        "AND qual LIKE '%COALESCE%'"
                    )
                    row = cur.fetchone()
                    coalesce_count = int(row[0]) if row else 0
            finally:
                conn.close()

            assert coalesce_count == 1, (
                f"After abort, expected COALESCE policy still present on project_states, "
                f"found {coalesce_count}"
            )


# ─────────────────────────────────────── DOWNGRADE / REAPPLY catalog


@requires_db
class TestDowngradeReapply:
    """Downgrade restores fail-open; re-apply closes again (idempotent)."""

    def test_downgrade_then_reapply_cycle(self, migrated_dsn) -> None:
        """Full downgrade → RED → re-apply → GREEN cycle on the migrated DB.

        This test owns the complete lifecycle verification for the downgrade path.
        """
        # Downgrade.
        _exec_sql(migrated_dsn, _emitted_sql("downgrade"))

        # Verify RED after downgrade.
        for table in COALESCE_TABLES:
            count = _count_as_role(migrated_dsn, table, tenant_guc=None)
            assert count > 0, (
                f"DOWNGRADE FAILED: {table} returned 0 rows without GUC "
                f"after downgrade — COALESCE not restored"
            )

        # Re-apply upgrade.
        _exec_sql(migrated_dsn, _emitted_sql("upgrade"))

        # Verify GREEN after re-apply.
        for table in COALESCE_TABLES:
            count = _count_as_role(migrated_dsn, table, tenant_guc=None)
            assert count == 0, (
                f"RE-APPLY FAILED: {table} returned {count} rows without GUC "
                f"after re-apply — NULLIF not re-applied"
            )


# ─────────────────────────────────────────── P0-SEC-A REGRESSION GUARD


@requires_db
class TestP0SecARegression:
    """P0-SEC-B must not affect tables hardened by P0-SEC-A."""

    def test_excess_policies_are_dropped(self, migrated_dsn) -> None:
        conn = _db_conn(migrated_dsn)
        try:
            with conn.cursor() as cur:
                for table, policy in EXCESS_POLICIES:
                    cur.execute(
                        "SELECT COUNT(*) FROM pg_policies "
                        "WHERE schemaname='public' AND tablename=%s AND policyname=%s",
                        (table, policy),
                    )
                    row = cur.fetchone()
                    count = int(row[0]) if row else 0
                    assert count == 0, (
                        f"Excess policy {policy} on {table} was not dropped"
                    )
        finally:
            conn.close()

    def test_canonical_crud_policies_survive_on_excess_tables(self, migrated_dsn) -> None:
        """The 4 canonical per-operation NULLIF policies must remain on each excess table."""
        conn = _db_conn(migrated_dsn)
        try:
            with conn.cursor() as cur:
                for table in ("analyses", "alerts", "coherence_results", "clause_embeddings"):
                    for op in ("select", "insert", "update", "delete"):
                        policy = f"{table}_tenant_isolation_{op}"
                        cur.execute(
                            "SELECT COUNT(*) FROM pg_policies "
                            "WHERE schemaname='public' AND tablename=%s AND policyname=%s",
                            (table, policy),
                        )
                        row = cur.fetchone()
                        count = int(row[0]) if row else 0
                        assert count == 1, (
                            f"Canonical policy {policy} on {table} is missing after migration"
                        )
        finally:
            conn.close()


# ─────────────────────────────── POSTGRES / BYPASSRLS COMPATIBILITY


@requires_db
class TestPostgresCompatibility:
    """Upgrade runs on plain PostgreSQL with no Supabase roles.

    The migration must not fail if anon/authenticated/service_role do not exist.
    This mirrors what happens in CI and local dev environments.
    """

    def test_upgrade_is_portable_without_supabase_roles(self) -> None:
        """The upgrade SQL must not reference Supabase-specific role names."""
        sql = _emitted_sql("upgrade")
        for role in ("anon", "authenticated", "service_role"):
            # Policy bodies must not grant/revoke to these roles directly.
            assert f"TO {role}" not in sql, f"upgrade references Supabase role {role}"
            assert f"FROM {role}" not in sql, f"upgrade references Supabase role {role}"

    def test_bypassrls_session_user_sees_everything_regardless(self, migrated_dsn) -> None:
        """A superuser / BYPASSRLS session bypasses RLS and always sees all rows.

        This confirms the migration does not accidentally break superuser access.
        The admin DSN connects as a BYPASSRLS user, so no GUC is needed.
        """
        conn = _db_conn(migrated_dsn)
        try:
            with conn.cursor() as cur:
                for table in COALESCE_TABLES:
                    cur.execute(f"SELECT COUNT(*) FROM {table}")  # nosec B608
                    row = cur.fetchone()
                    count = int(row[0]) if row else 0
                    assert count == 2, (
                        f"BYPASSRLS session sees {count} rows in {table}, expected 2 "
                        f"(all seed rows should be visible to superuser)"
                    )
        finally:
            conn.close()


# ──────────────────────────────────────── DUAL-PATH CATALOG PARITY GATE


def _query_policies(dsn: str, table: str) -> list[dict]:
    """Return ordered pg_policies rows for *table* as plain dicts."""
    conn = _db_conn(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT policyname, cmd, permissive, roles, qual, with_check "
                "FROM pg_policies "
                "WHERE schemaname = 'public' AND tablename = %s "
                "ORDER BY policyname",
                (table,),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
    finally:
        conn.close()


@requires_db
class TestDualPathCatalogParity:
    """Prove PATH A (Alembic prestate + upgrade) and PATH B (Supabase-historical
    prestate + mirror SQL) converge to an identical pg_policies catalog.

    PATH A uses migrated_dsn  — Alembic COALESCE prestate + _emitted_sql("upgrade").
    PATH B uses supabase_migrated_dsn — Supabase NULLIF *_tenant_isolation_* prestate
                                        + MIRROR.read_text() (checked-in mirror SQL).
    """

    @pytest.mark.parametrize("table", COALESCE_TABLES)
    def test_both_paths_produce_identical_policy_catalog(
        self, migrated_dsn, supabase_migrated_dsn, table
    ) -> None:
        path_a = _query_policies(migrated_dsn, table)
        path_b = _query_policies(supabase_migrated_dsn, table)
        assert path_a == path_b, (
            f"pg_policies DIVERGE for {table}:\n"
            f"  PATH A (Alembic): {path_a}\n"
            f"  PATH B (Supabase): {path_b}"
        )

    @pytest.mark.parametrize("table", COALESCE_TABLES)
    def test_exactly_4_policies_per_coalesce_table_both_paths(
        self, migrated_dsn, supabase_migrated_dsn, table
    ) -> None:
        for label, dsn in (("PATH A", migrated_dsn), ("PATH B", supabase_migrated_dsn)):
            policies = _query_policies(dsn, table)
            assert len(policies) == 4, (
                f"{label}: {table} has {len(policies)} policies, expected exactly 4. "
                f"Policies: {[p['policyname'] for p in policies]}"
            )

    def test_zero_legacy_tenant_isolation_names_both_paths(
        self, migrated_dsn, supabase_migrated_dsn
    ) -> None:
        for label, dsn in (("PATH A", migrated_dsn), ("PATH B", supabase_migrated_dsn)):
            conn = _db_conn(dsn)
            try:
                with conn.cursor() as cur:
                    # Pass the LIKE pattern as a bind parameter; embedding '%'
                    # in the SQL string alongside other %s params confuses psycopg3.
                    cur.execute(
                        "SELECT tablename, policyname FROM pg_policies "
                        "WHERE schemaname = 'public' "
                        "AND policyname LIKE %s "
                        "AND tablename = ANY(%s)",
                        ("%tenant_isolation%", list(COALESCE_TABLES)),
                    )
                    survivors = cur.fetchall()
            finally:
                conn.close()
            assert survivors == [], (
                f"{label}: *tenant_isolation* names survive on COALESCE tables after migration: "
                f"{survivors}"
            )

    def test_zero_coalesce_expressions_both_paths(
        self, migrated_dsn, supabase_migrated_dsn
    ) -> None:
        for label, dsn in (("PATH A", migrated_dsn), ("PATH B", supabase_migrated_dsn)):
            conn = _db_conn(dsn)
            try:
                with conn.cursor() as cur:
                    # Pass ILIKE patterns as bind parameters to avoid psycopg3
                    # interpreting the embedded '%' as a placeholder prefix.
                    cur.execute(
                        "SELECT tablename, policyname, qual, with_check "
                        "FROM pg_policies "
                        "WHERE schemaname = 'public' "
                        "AND tablename = ANY(%s) "
                        "AND (qual ILIKE %s OR with_check ILIKE %s)",
                        (list(COALESCE_TABLES), "%COALESCE%", "%COALESCE%"),
                    )
                    coalesce_rows = cur.fetchall()
            finally:
                conn.close()
            assert coalesce_rows == [], (
                f"{label}: COALESCE found in pg_policies qual/with_check after migration: "
                f"{coalesce_rows}"
            )

    @pytest.mark.parametrize("table", COALESCE_TABLES)
    def test_supabase_path_guc_absent_sees_no_rows(
        self, supabase_migrated_dsn, table
    ) -> None:
        count = _count_as_role(supabase_migrated_dsn, table, tenant_guc=None)
        assert count == 0, (
            f"PATH B: {table} returned {count} rows with GUC absent after mirror — "
            f"NULLIF fail-closed not in effect"
        )

    @pytest.mark.parametrize("table", COALESCE_TABLES)
    def test_supabase_path_empty_guc_sees_no_rows(
        self, supabase_migrated_dsn, table
    ) -> None:
        count = _count_as_role(supabase_migrated_dsn, table, tenant_guc="")
        assert count == 0, (
            f"PATH B: {table} returned {count} rows with empty GUC after mirror — "
            f"NULLIF fail-closed not in effect"
        )

    @pytest.mark.parametrize("table", COALESCE_TABLES)
    def test_supabase_path_tenant_a_sees_own_rows(
        self, supabase_migrated_dsn, table
    ) -> None:
        count = _count_as_role(supabase_migrated_dsn, table, tenant_guc=TENANT_A)
        assert count == 1, (
            f"PATH B: {table}: TENANT_A sees {count} rows, expected 1"
        )

    @pytest.mark.parametrize("table", COALESCE_TABLES)
    def test_supabase_path_tenant_b_sees_own_rows(
        self, supabase_migrated_dsn, table
    ) -> None:
        count = _count_as_role(supabase_migrated_dsn, table, tenant_guc=TENANT_B)
        assert count == 1, (
            f"PATH B: {table}: TENANT_B sees {count} rows, expected 1"
        )
