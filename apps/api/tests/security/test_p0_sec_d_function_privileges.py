"""P0-SEC-D: SECURITY DEFINER function-privilege hardening tests.

CLASSIFICATION: DEFENSE_IN_DEPTH / privilege-boundary hardening, not a
confirmed exploitable path. public.handle_new_user() is SECURITY DEFINER
with an owner that carries BYPASSRLS in production, and PUBLIC/anon/
authenticated/service_role all hold EXECUTE on it (pre-fix) -- but two
independent PostgreSQL behaviors already block the only two ways to invoke
it: (1) direct invocation is rejected outright ("trigger functions can only
be called as triggers"), and (2) attaching it to a *new* trigger requires
EXECUTE on it AND either CREATE on some schema or TRIGGER on some existing
table, neither of which anon/authenticated hold anywhere in schema public
post-P0-SEC-A (verified: has_schema_privilege('authenticated', 'public',
'CREATE') = false; zero rows in information_schema.role_table_grants for
anon/authenticated with privilege_type='TRIGGER'). No reachable path from
the EXECUTE grant to the SECURITY DEFINER execution context is demonstrated.

The REVOKE is still justified as consistency and defense-in-depth: every
other SECURITY DEFINER function in this codebase (public.
create_tenant_and_owner, all 7 auth_bootstrap.* functions) explicitly
revokes PUBLIC/anon/authenticated; this one did not, for no documented
reason, and the ACL would become live risk again the moment either
prerequisite privilege is ever (re)granted for an unrelated purpose.

RED against the pre-fix committed state:
    PostgreSQL's default (and, on production's actual pg_default_acl
    posture, an explicit per-role default-privilege grant) leaves
    handle_new_user() executable by PUBLIC, anon, authenticated, and
    service_role.

GREEN after the fix:
    The new migration (20260906000100_p0_sec_d_function_privileges.sql)
    revokes ALL from PUBLIC, anon, authenticated, and service_role, guarded
    by an existence check so it is a no-op on the Alembic-only path (where
    this Supabase-Auth-integration function never existed).

* **Static** checks (this file's ``TestMigrationShape``) require no
  database and always run.
* **Catalog** checks (``TestCatalogGate``) run only when ``P0_SEC_D_TEST_DSN``
  points at a loopback admin DSN, mirroring
  ``tests/security/test_p0_sec_b_fail_closed_migration.py``. The standalone,
  more exhaustive RED->GREEN->regression-proof cycle lives in
  ``apps/api/scripts/p0_sec_d_gate.py``; these tests are a lighter pytest-
  native integration smoke test over the same fixture and migration.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "apps/api/scripts"))

import p0_sec_d_common as _common  # noqa: E402
import supabase_security_lint as _lint  # noqa: E402
from security_gate_common import exec_sql, is_loopback_dsn  # noqa: E402

pytestmark = pytest.mark.security

_RAW_DSN = os.environ.get("P0_SEC_D_TEST_DSN")
DSN = _RAW_DSN if _RAW_DSN and is_loopback_dsn(_RAW_DSN) else None
requires_db = pytest.mark.skipif(
    not DSN,
    reason="set P0_SEC_D_TEST_DSN to a loopback admin DSN to run catalog checks",
)


# ═══════════════════════════════════════════════════════════ static checks


class TestMigrationShape:
    def test_fix_migration_exists(self) -> None:
        assert _common.FIX_MIGRATION_PATH.exists(), (
            f"{_common.FIX_MIGRATION_PATH} is missing"
        )

    def test_fix_migration_is_guarded_by_exact_function_identity(self) -> None:
        """Must be a no-op where handle_new_user() never existed (Alembic path),

        and must resolve the exact (schema, name, argument-type) identity via
        to_regprocedure -- not merely proname -- so a future overload named
        handle_new_user with different arguments cannot make the guard true
        while the zero-argument function itself is absent.
        """
        sql = _common.fix_migration_sql()
        assert "to_regprocedure('public.handle_new_user()')" in sql
        assert "IS NOT NULL" in sql

    def test_fix_migration_revokes_all_four_roles(self) -> None:
        sql = _common.fix_migration_sql()
        assert "REVOKE ALL ON FUNCTION public.handle_new_user()" in sql
        for role in ("PUBLIC", "anon", "authenticated", "service_role"):
            assert role in sql, f"fix migration does not mention role {role!r}"

    def test_extracted_handle_new_user_ddl_is_security_definer(self) -> None:
        """Guards the extractor itself: if init_schema.sql ever drops

        SECURITY DEFINER from handle_new_user(), this fix's premise (and the
        gate's RED phase) would silently stop applying to anything.
        """
        ddl = _common.extract_handle_new_user_ddl()
        assert "SECURITY DEFINER" in ddl
        assert "CREATE TRIGGER on_auth_user_created" in ddl

    def test_no_alembic_counterpart_exists(self) -> None:
        """handle_new_user() must not exist on the Alembic path -- if it ever

        does, this Supabase-only fix would leave that path unprotected.
        """
        alembic_versions = REPO_ROOT / "apps/api/alembic/versions"
        for path in alembic_versions.glob("*.py"):
            if "handle_new_user" in path.read_text(encoding="utf-8"):
                pytest.fail(
                    f"{path} references handle_new_user(); the P0-SEC-D fix "
                    "migration only covers the Supabase path and must be "
                    "extended for Alembic too"
                )


# ═══════════════════════════════════════════════════════ catalog checks


@requires_db
class TestCatalogGate:
    def _build_prefix_db(self, dsn: str) -> None:
        exec_sql(dsn, path=_common.FIXTURE_PATH)
        exec_sql(
            dsn,
            sql=f"SET ROLE c2pro_owner;\n{_common.extract_handle_new_user_ddl()}\nRESET ROLE;",
        )

    def test_prefix_state_is_blocking(self, disposable_db: str) -> None:
        self._build_prefix_db(disposable_db)
        assert _lint.run(disposable_db, scope="p0_sec_d") == 1, (
            "lint did not flag the pre-fix state as BLOCKING -- "
            "the p0_sec_d check has lost its teeth"
        )

    def test_postfix_state_is_clean(self, disposable_db: str) -> None:
        self._build_prefix_db(disposable_db)
        exec_sql(disposable_db, sql=_common.fix_migration_sql())
        assert _lint.run(disposable_db, scope="p0_sec_d") == 0, (
            "lint still reports a violation after the fix migration was applied"
        )


@pytest.fixture
def disposable_db() -> str:
    """Create and drop a scratch database on the loopback admin DSN."""
    admin = DSN
    assert admin is not None  # guarded by requires_db
    db_name = "p0_sec_d_pytest_scratch"
    target = admin.rsplit("/", 1)[0] + "/" + db_name

    exec_sql(admin, sql=f'DROP DATABASE IF EXISTS "{db_name}"')
    exec_sql(admin, sql=f'CREATE DATABASE "{db_name}"')
    try:
        yield target
    finally:
        exec_sql(admin, sql=f'DROP DATABASE IF EXISTS "{db_name}"')
