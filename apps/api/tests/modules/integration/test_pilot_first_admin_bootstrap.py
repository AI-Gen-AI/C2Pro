"""Pilot first-admin bootstrap: every gate refuses, the default is a non-mutating dry-run, apply is atomic.

Unit tests (no database) cover the CLI gates, the Clerk proof and the read-only default. The ``*_pg`` tests reuse the
S5 grants world on a real PostgreSQL (the shared ``db`` fixture) and are the only ones that need a database.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from scripts import pilot_first_admin_bootstrap as boot
from scripts.pilot_first_admin_bootstrap import BootstrapRefused, Request
from tests.modules.integration.grants_world import GrantsWorld, build_world

OK_ENV = {
    "RAILWAY_PROJECT_ID": boot.PILOT_RAILWAY_PROJECT_ID,
    "RAILWAY_ENVIRONMENT_ID": boot.PILOT_RAILWAY_ENVIRONMENT_ID,
}
REASON = "single human on the pilot tenant until a second admin is invited"


def _req(**kw: Any) -> Request:
    base = Request(
        uuid4(), uuid4(), "user_abc", "OWNER-APPROVED:ticket-0001", "operator_x", apply=True
    )
    return replace(base, **kw)


def _clerk(email: str = "a@example.invalid", **over: Any) -> Any:
    user = {
        "id": "user_abc",
        "banned": False,
        "locked": False,
        "primary_email_address_id": "e1",
        "email_addresses": [
            {"id": "e1", "email_address": email, "verification": {"status": "verified"}}
        ],
        **over,
    }
    return lambda path, _s: (
        {"data": [{"organization": {"id": "org_1"}}]}
        if "organization_memberships" in path
        else user
    )


@pytest.mark.parametrize(
    ("env", "req", "code"),
    [
        ({**OK_ENV, "RAILWAY_PROJECT_ID": "other"}, _req(), "RAILWAY_PROJECT"),
        ({**OK_ENV, "RAILWAY_ENVIRONMENT_ID": "other"}, _req(), "RAILWAY_ENVIRONMENT"),
        ({}, _req(), "RAILWAY_PROJECT"),
        (OK_ENV, _req(owner_marker=""), "OWNER_AUTHORIZATION"),
        (OK_ENV, _req(owner_marker="OWNER-APPROVED:"), "OWNER_AUTHORIZATION"),
        (OK_ENV, _req(owner_marker="approved by me, trust me"), "OWNER_AUTHORIZATION"),
        (OK_ENV, _req(self_review_reason="short"), "SELF_REVIEW_REASON"),
        (OK_ENV, _req(clerk_user_id="not-a-clerk-id"), "CLERK_USER_ID"),
    ],
)
def test_apply_gates_refuse(env: dict[str, str], req: Request, code: str) -> None:
    with pytest.raises(BootstrapRefused, match=code):
        boot.check_gates(req, env)


def test_apply_gates_pass_only_when_everything_is_explicit() -> None:
    boot.check_gates(_req(), OK_ENV)
    boot.check_gates(_req(self_review_reason=REASON), OK_ENV)


def test_the_parser_defaults_to_dry_run_and_self_review_is_a_separate_opt_in() -> None:
    args = boot.build_parser().parse_args(
        [
            "--tenant-id",
            str(uuid4()),
            "--user-id",
            str(uuid4()),
            "--clerk-user-id",
            "user_x",
            "--owner-authorization-marker",
            "OWNER-APPROVED:t",
            "--operator-role",
            "op",
        ]
    )
    assert args.apply is False and args.non_independent_self_review_with_reason is None


def test_clerk_proof_passes_and_returns_no_payload() -> None:
    proof = boot.verify_clerk(_req(), "a@example.invalid", "org_1", _clerk())
    assert proof == {
        "clerk_active": True,
        "email_verified": True,
        "email_matches_db": True,
        "org_member": True,
    }


@pytest.mark.parametrize(
    ("over", "email", "org", "code"),
    [
        ({"banned": True}, "a@example.invalid", None, "NOT_FOUND_OR_NOT_ACTIVE"),
        ({"locked": True}, "a@example.invalid", None, "NOT_FOUND_OR_NOT_ACTIVE"),
        ({"id": "user_other"}, "a@example.invalid", None, "NOT_FOUND_OR_NOT_ACTIVE"),
        ({"primary_email_address_id": "missing"}, "a@example.invalid", None, "EMAIL_NOT_VERIFIED"),
        ({}, "someone-else@example.invalid", None, "DOES_NOT_MATCH_DB_USER"),
        ({}, "a@example.invalid", "org_2", "NOT_A_MEMBER_OF_THE_TENANT_ORG"),
    ],
)
def test_clerk_proof_refuses(over: dict[str, Any], email: str, org: str | None, code: str) -> None:
    with pytest.raises(BootstrapRefused, match=code):
        boot.verify_clerk(_req(), email, org, _clerk(**over))


def test_clerk_unverifiable_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLERK_SECRET_KEY", raising=False)
    with pytest.raises(BootstrapRefused, match="NO_BACKEND_SECRET"):
        boot.verify_clerk(_req(), "a@example.invalid", None, None)

    def down(_p: str, _s: str) -> dict[str, Any]:
        raise TimeoutError("https://api.clerk.com/v1/users/user_abc")

    with pytest.raises(BootstrapRefused, match="API_UNAVAILABLE") as err:
        boot.verify_clerk(_req(), "a@example.invalid", None, down)
    assert "user_abc" not in str(err.value) and "clerk.com" not in str(err.value)


def test_fingerprints_do_not_contain_the_value() -> None:
    assert boot.fp("user_abc").startswith("fp_") and "user_abc" not in boot.fp("user_abc")


@pytest.mark.asyncio
async def test_dry_run_refuses_the_wrong_role_before_reading_anything_else() -> None:
    class Recorder:
        statements: list[str] = []

        async def execute(self, statement: Any, params: Any = None) -> Any:
            sql = str(statement)
            self.statements.append(sql)
            assert not sql.lstrip().upper().startswith(("UPDATE", "INSERT", "DELETE")), (
                "dry-run must not write"
            )

            class Result:
                def one(self_inner) -> tuple[str, bool]:  # noqa: N805
                    return ("authenticated", False)

            return Result()

    session = Recorder()
    with pytest.raises(BootstrapRefused, match="DB_ROLE_IS_NOT_THE_DECLARED_OPERATOR_ROLE"):
        await boot.execute(session, _req(apply=False, operator_role="authenticated"))  # type: ignore[arg-type]
    assert session.statements[0] == "SET TRANSACTION READ ONLY"


# --- PostgreSQL: the S5 grants world; tenant A is turned into a zero-admin pilot tenant -----------------------------


async def _pilot(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch, *, mode: str = "off"
) -> tuple[GrantsWorld, Request, Any]:
    w = await build_world(db, mode=mode)
    monkeypatch.setattr(boot, "PILOT_PROJECT_ID", w.p1)
    await db.execute(text("UPDATE users SET role = 'user' WHERE id = :u"), {"u": w.admin_a})
    await db.execute(
        text("UPDATE users SET clerk_user_id = :c WHERE id = :u"),
        {"c": f"user_{uuid4().hex}", "u": w.reviewer_a},
    )
    await db.commit()
    row = (
        await db.execute(
            text("SELECT clerk_user_id, email FROM users WHERE id = :u"), {"u": w.reviewer_a}
        )
    ).one()
    org = (
        await db.execute(text("SELECT clerk_org_id FROM tenants WHERE id = :t"), {"t": w.tenant_a})
    ).scalar_one()
    me = (await db.execute(text("SELECT current_user"))).scalar_one()
    await db.rollback()
    req = Request(w.tenant_a, w.reviewer_a, row[0], "OWNER-APPROVED:ticket-0001", me, apply=True)

    def fetch(path: str, _s: str) -> dict[str, Any]:
        if "organization_memberships" in path:
            return {"data": [{"organization": {"id": org}}]}
        return {
            "id": row[0],
            "banned": False,
            "locked": False,
            "primary_email_address_id": "e1",
            "email_addresses": [
                {"id": "e1", "email_address": row[1], "verification": {"status": "verified"}}
            ],
        }

    return w, req, fetch


async def _snapshot(db: AsyncSession) -> tuple[Any, ...]:
    await db.rollback()
    q = lambda s: text(s)  # noqa: E731
    return (
        (
            await db.execute(
                q("SELECT string_agg(id::text || role::text, ',' ORDER BY id) FROM users")
            )
        ).scalar_one(),
        (await db.execute(q("SELECT count(*) FROM project_review_grants"))).scalar_one(),
        (
            await db.execute(
                q(
                    "SELECT count(*) FROM project_events WHERE event_type = 'hitl.first_admin_bootstrap'"
                )
            )
        ).scalar_one(),
        (
            await db.execute(q("SELECT string_agg(settings::text, ',' ORDER BY id) FROM tenants"))
        ).scalar_one(),
    )


@pytest.mark.asyncio
async def test_dry_run_reads_only_and_reports_counts_pg(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    _w, req, fetch = await _pilot(db, monkeypatch)
    before = await _snapshot(db)
    report = await boot.execute(db, replace(req, apply=False), clerk_fetch=fetch)
    await db.rollback()
    assert (
        report["mode"] == "DRY_RUN"
        and report["apply_ready"] is True
        and report["active_admins"] == 0
    )
    assert "@" not in str(report) and req.clerk_user_id not in str(report)
    assert await _snapshot(db) == before


@pytest.mark.asyncio
async def test_apply_promotes_only_the_selected_user_and_audits_pg(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    w, req, fetch = await _pilot(db, monkeypatch)
    report = await boot.execute(db, req, env=OK_ENV, clerk_fetch=fetch)
    await db.commit()
    assert report["applied"] is True and report["grants"] == []
    roles = dict(
        (
            await db.execute(
                text("SELECT id, role::text FROM users WHERE tenant_id = :t"), {"t": w.tenant_a}
            )
        ).all()
    )
    assert [u for u, r in roles.items() if r == "admin"] == [w.reviewer_a]
    payload = (
        await db.execute(
            text(
                "SELECT payload::text FROM project_events WHERE event_type = 'hitl.first_admin_bootstrap'"
            )
        )
    ).scalar_one()
    assert "fp_" in payload and "@" not in payload and req.clerk_user_id not in payload
    assert (
        await db.execute(text("SELECT count(*) FROM project_review_grants"))
    ).scalar_one() == 0, "no self-review opt-in: no grants"
    assert (
        await db.execute(text("SELECT role::text FROM users WHERE id = :u"), {"u": w.user_b})
    ).scalar_one() == "user", "other tenant untouched"


@pytest.mark.asyncio
async def test_apply_is_one_time_a_second_run_is_refused_pg(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    _w, req, fetch = await _pilot(db, monkeypatch)
    await boot.execute(db, req, env=OK_ENV, clerk_fetch=fetch)
    await db.commit()
    with pytest.raises(BootstrapRefused, match="ALREADY_HAS_AN_ACTIVE_ADMIN|USER_ROLE_IS_NOT_USER"):
        await boot.execute(db, req, env=OK_ENV, clerk_fetch=fetch)
    await db.rollback()


@pytest.mark.asyncio
async def test_self_review_creates_the_three_governed_grants_and_enforces_pg(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    w, req, fetch = await _pilot(db, monkeypatch)
    report = await boot.execute(
        db, replace(req, self_review_reason=REASON), env=OK_ENV, clerk_fetch=fetch
    )
    await db.commit()
    assert report["post"]["mode"] == "enforce" and report["post"]["capabilities"] == 3
    rows = (
        await db.execute(
            text(
                "SELECT permission, user_id, granted_by, self_grant_exception FROM project_review_grants WHERE revoked_at IS NULL"
            )
        )
    ).all()
    assert sorted(r[0] for r in rows) == sorted(c.value for c in boot.CAPABILITIES)
    assert all(r[1] == w.reviewer_a and r[2] == w.reviewer_a and r[3] is True for r in rows)
    assert (
        await db.execute(
            text(
                "SELECT settings #>> '{hitl_project_authorization,mode}' FROM tenants WHERE id = :t"
            ),
            {"t": w.tenant_a},
        )
    ).scalar_one() == "enforce"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        "existing_admin",
        "wrong_clerk_id",
        "viewer",
        "other_tenant_user",
        "inactive",
        "runtime_role",
        "clerk_down",
    ],
)
async def test_every_failed_precheck_writes_nothing_pg(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    w, req, fetch = await _pilot(db, monkeypatch)
    if case == "existing_admin":
        await db.execute(text("UPDATE users SET role = 'admin' WHERE id = :u"), {"u": w.admin_a})
    elif case == "wrong_clerk_id":
        req = replace(req, clerk_user_id="user_someone_else")
    elif case == "viewer":
        await db.execute(
            text("UPDATE users SET role = 'viewer' WHERE id = :u"), {"u": w.reviewer_a}
        )
    elif case == "other_tenant_user":
        req = replace(req, user_id=w.user_b)
    elif case == "inactive":
        await db.execute(
            text("UPDATE users SET is_active = false WHERE id = :u"), {"u": w.reviewer_a}
        )
    elif case == "runtime_role":
        req = replace(req, operator_role="authenticated")
    elif case == "clerk_down":

        def fetch(_p: str, _s: str) -> dict[str, Any]:  # noqa: F811
            raise TimeoutError

    await db.commit()
    before = await _snapshot(db)
    with pytest.raises(BootstrapRefused):
        await boot.execute(
            db, replace(req, self_review_reason=REASON), env=OK_ENV, clerk_fetch=fetch
        )
    await db.rollback()
    assert await _snapshot(db) == before
