"""S5-01/S5-02: static contract of the grants migration, its Supabase mirror, the event types and the grant script.

The behaviour (privileges, RLS, atomicity, concurrency, org switch, enforcement) is proven on PostgreSQL in
``tests/modules/integration/test_s5_project_review_grants_security_pg.py`` and ``..._authorization_pg.py``.
"""

from __future__ import annotations

import sys
import types
from importlib import util
from pathlib import Path

import pytest

from src.modules.hitl.application.project_review_authorization import (
    AuthorizationMode,
    ProjectCapability,
    transitional_off_setting,
)
from src.temporal.domain.event_type import KNOWN_EVENT_TYPES

API = Path(__file__).resolve().parents[4]
MIGRATION = API / "alembic/versions/20261101_0001_s5_project_review_grants.py"
VERSIONS = API / "alembic/versions"


def _migration():
    stub = types.SimpleNamespace(op=types.SimpleNamespace(execute=lambda *_: None))
    previous = sys.modules.get("alembic")
    sys.modules["alembic"] = stub  # type: ignore[assignment]
    try:
        spec = util.spec_from_file_location("s5_grants_contract_migration", MIGRATION)
        assert spec is not None and spec.loader is not None
        module = util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if previous is not None:
            sys.modules["alembic"] = previous
        else:
            sys.modules.pop("alembic", None)


def test_the_supabase_mirror_is_exactly_what_the_migration_generates_and_the_chain_has_one_head() -> (
    None
):
    migration = _migration()
    mirror = API.parents[1] / "supabase/migrations" / migration.SUPABASE_MIRROR
    assert mirror.read_text() == migration.supabase_sql()
    assert migration.revision == "20261101_0001"
    assert migration.down_revision == "20261022_0001"
    successors = [
        p.name
        for p in VERSIONS.glob("*.py")
        if f'down_revision = "{migration.revision}"' in p.read_text()
    ]
    assert successors == [], (
        "this migration must be the head until another one is added deliberately"
    )
    same_parent = [
        p.name
        for p in VERSIONS.glob("*.py")
        if f'down_revision = "{migration.down_revision}"' in p.read_text()
    ]
    assert same_parent == [MIGRATION.name], "two migrations share one parent: the chain would fork"


def test_the_ddl_is_forced_rls_no_delete_no_public_and_no_composite_key_to_users() -> None:
    ddl = _migration().supabase_sql()
    assert "ENABLE ROW LEVEL SECURITY" in ddl and "FORCE ROW LEVEL SECURITY" in ddl
    assert "FOR SELECT USING" in ddl and "FOR INSERT WITH CHECK" in ddl
    assert "FOR DELETE" not in ddl.replace("BEFORE INSERT OR UPDATE OR DELETE", ""), (
        "no DELETE policy exists"
    )
    assert "REVOKE ALL ON TABLE public.project_review_grants FROM PUBLIC" in ddl
    assert "anon" in ddl and "authenticated" in ddl
    assert "GRANT ALL" not in ddl
    assert "SECURITY DEFINER" in ddl
    # The first proposal (rejected, see test_s5_org_switch_principal_pg): it makes the Clerk org switch fail.
    assert (
        "REFERENCES public.users (tenant_id" not in ddl and "REFERENCES users (tenant_id" not in ddl
    )
    assert "app.project_review_grants_writer" in ddl, "writes only through the governed functions"


def test_the_downgrade_removes_only_what_the_upgrade_created() -> None:
    migration = _migration()
    joined = "\n".join(migration.DOWNGRADE_STATEMENTS)
    assert "project_review_grants" in joined
    assert "DROP TABLE" in joined and "DROP FUNCTION" in joined
    assert "tenants" not in joined.split("DROP TABLE")[0] or "hitl_project_authorization" in joined


def test_the_three_capabilities_are_distinct_and_the_audit_events_are_registered() -> None:
    assert {c.value for c in ProjectCapability} == {
        "READ_REVIEW",
        "REVIEW_FINDING",
        "APPROVE_CANDIDATE",
    }
    assert {"hitl.project_grant_created", "hitl.project_grant_revoked"} <= KNOWN_EVENT_TYPES


def test_the_transitional_marker_says_it_is_not_secure_and_carries_its_reason() -> None:
    marker = transitional_off_setting("because")
    assert marker == {
        "mode": AuthorizationMode.OFF.value,
        "transitional": True,
        "reason": "because",
    }


# ── the grant script ─────────────────────────────────────────────────────────────────────────────────────────
def _script():
    from scripts import grant_project_review_permissions as script

    return script


def test_the_script_refuses_apply_unless_it_is_an_isolated_local_test_database() -> None:
    script = _script()
    local = {
        "ENVIRONMENT": "test",
        "DATABASE_URL": "postgresql+asyncpg://u:p@localhost:5433/c2pro_test",
    }
    script.require_isolated_test_database(confirmed=True, env=local)
    for env, confirmed, code in (
        (local, False, "APPLY_REQUIRES_--confirm-isolated-test-database"),
        ({**local, "ENVIRONMENT": "production"}, True, "APPLY_REQUIRES_ENVIRONMENT_TEST"),
        ({**local, "ENVIRONMENT": ""}, True, "APPLY_REQUIRES_ENVIRONMENT_TEST"),
        (
            {
                **local,
                "DATABASE_URL": "postgresql+asyncpg://u:p@db.example.supabase.co:5432/postgres",
            },
            True,
            "APPLY_REFUSES_NON_LOOPBACK_DATABASE",
        ),
        ({"ENVIRONMENT": "test"}, True, "APPLY_REFUSES_NON_LOOPBACK_DATABASE"),
    ):
        with pytest.raises(script.GrantScriptError, match=code):
            script.require_isolated_test_database(confirmed=confirmed, env=env)


def test_the_script_is_a_dry_run_by_default_and_never_touches_a_database(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _script()
    ids = [f"00000000-0000-0000-0000-00000000000{i}" for i in range(1, 5)]
    argv = [
        "grant",
        "--tenant",
        ids[0],
        "--project",
        ids[1],
        "--user",
        ids[2],
        "--capability",
        "APPROVE_CANDIDATE",
        "--granted-by",
        ids[3],
        "--reason",
        "UAT approver",
    ]
    assert script.main(argv) == 0
    out = capsys.readouterr().out
    assert "DRY-RUN: nothing was written" in out and "APPROVE_CANDIDATE" in out
    # --apply without the explicit confirmation is refused before any connection is attempted
    assert script.main([*argv, "--apply"]) == 3
    with pytest.raises(
        SystemExit
    ):  # an unknown capability is rejected by the parser, never passed on
        script.build_parser().parse_args(
            [
                "grant",
                "--tenant",
                ids[0],
                "--project",
                ids[1],
                "--user",
                ids[2],
                "--capability",
                "ADMIN",
                "--granted-by",
                ids[3],
                "--reason",
                "x",
            ]
        )
