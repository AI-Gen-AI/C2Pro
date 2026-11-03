"""The command-line entry points of the integral S1-S8 UAT, run end to end against a SIMULATED Clerk (httpx
MockTransport) and a fake database: no network, no secret, no write to Clerk.

Every simulated Clerk answer asserts the request is a GET: the preflight and the discovery are read-only by
construction, and these tests would fail the moment either of them tried to write.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from scripts import discover_integral_dev_identities as discovery
from scripts import preflight_integral_identities as preflight
from scripts import verify_integral_s1_s8_pg as verifier
from scripts import write_integral_runtime_receipt as receipt_script
from tests.unit.scripts.test_integral_s1_s8_runner import _world

REAL_CLIENT = httpx.Client
A_TENANT = preflight.SEED_TENANT_A
B_TENANT = "00000000-0000-0000-0000-00000000a114"
KEY = {"kty": "RSA", "kid": "ins_1", "n": "abc", "e": "AQAB"}


def _user(user_id: str, email: str, **extra: Any) -> dict[str, Any]:
    return {"id": user_id, "email_addresses": [{"email_address": email}], **extra}


def _membership(org: str, tenant: str) -> dict[str, Any]:
    return {"organization": {"id": org, "public_metadata": {"tenant_id": tenant}}}


class FakeClerk:
    """users: id -> (email, extra); memberships: id -> list; jwks: the instance document."""

    def __init__(
        self, users: dict[str, tuple[str, dict]], memberships: dict[str, list], jwks: Any = None
    ) -> None:
        self.users, self.memberships = users, memberships
        self.jwks = jwks if jwks is not None else {"keys": [KEY]}
        self.methods: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.methods.append(request.method)
        assert request.method == "GET", (
            f"a read-only job attempted {request.method} {request.url.path}"
        )
        path = request.url.path.removeprefix("/v1")
        if path == "/jwks":
            return httpx.Response(200, json=self.jwks)
        if path == "/users/count":
            return httpx.Response(200, json={"total_count": len(self.users)})
        if path == "/users":
            wanted = request.url.params.get_list("email_address")
            rows = [_user(uid, email, **extra) for uid, (email, extra) in self.users.items()]
            if wanted:
                rows = [r for r in rows if r["email_addresses"][0]["email_address"] in wanted]
            offset = int(request.url.params.get("offset", 0))
            return httpx.Response(200, json=rows[offset : offset + 100])
        if path.endswith("/organization_memberships"):
            uid = path.split("/")[2]
            return httpx.Response(200, json=self.memberships.get(uid, []))
        return httpx.Response(404, json={})


@pytest.fixture
def clerk_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    for name in (
        "INTEGRAL_CLERK_DEV_B_EMAIL",
        "E2E_CLERK_TENANT_B_USER_EMAIL",
        "INTEGRAL_SYNTHETIC_EMAIL_DOMAINS",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_unit")
    monkeypatch.setenv("CLERK_PUBLISHABLE_KEY", "pk_test_unit")
    monkeypatch.setenv("E2E_CLERK_USER_EMAIL", "a@example.test")
    monkeypatch.setenv("INTEGRAL_CLERK_DEV_B_EMAIL", "b@example.test")
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    github_env = tmp_path / "github_env"
    github_env.write_text("")
    monkeypatch.setenv("GITHUB_ENV", str(github_env))
    return tmp_path


def _serve(monkeypatch: pytest.MonkeyPatch, clerk: FakeClerk) -> None:
    def factory(**kwargs: Any) -> httpx.Client:
        return REAL_CLIENT(
            transport=httpx.MockTransport(clerk.handler), headers=kwargs.get("headers")
        )

    monkeypatch.setattr(httpx, "Client", factory)


def _ready_clerk() -> FakeClerk:
    return FakeClerk(
        {"user_a": ("a@example.test", {}), "user_b": ("b@example.test", {})},
        {"user_a": [_membership("org_a", A_TENANT)], "user_b": [_membership("org_b", B_TENANT)]},
    )


# ── preflight ────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_preflight_exports_both_identities_and_a_validated_jwks_without_writing_to_clerk(
    monkeypatch: pytest.MonkeyPatch, clerk_env: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    clerk = _ready_clerk()
    _serve(monkeypatch, clerk)

    assert preflight.main(["--export-github-env"]) == preflight.READY

    exported = (clerk_env / "github_env").read_text()
    assert "CLERK_E2E_ORG_ID=org_a" in exported
    assert "TENANT_B_CLERK_E2E_ORG_ID=org_b" in exported
    assert json.loads((clerk_env / "clerk-jwks.json").read_text())["keys"][0]["kid"] == "ins_1"
    assert set(clerk.methods) == {"GET"}
    printed = capsys.readouterr().out
    assert "org_a" not in printed
    assert "user_a" not in printed


def test_the_preflight_without_the_export_flag_writes_nothing(
    monkeypatch: pytest.MonkeyPatch, clerk_env: Path
) -> None:
    _serve(monkeypatch, _ready_clerk())
    assert preflight.main([]) == preflight.READY
    assert (clerk_env / "github_env").read_text() == ""
    assert not (clerk_env / "clerk-jwks.json").exists()


def test_the_preflight_fails_closed_when_b_does_not_exist(
    monkeypatch: pytest.MonkeyPatch, clerk_env: Path
) -> None:
    clerk = FakeClerk(
        {"user_a": ("a@example.test", {})}, {"user_a": [_membership("org_a", A_TENANT)]}
    )
    _serve(monkeypatch, clerk)
    assert preflight.main(["--export-github-env"]) == preflight.FAILED
    assert (clerk_env / "github_env").read_text() == ""


def test_the_preflight_asks_for_preparation_when_b_has_no_organization(
    monkeypatch: pytest.MonkeyPatch, clerk_env: Path
) -> None:
    clerk = FakeClerk(
        {"user_a": ("a@example.test", {}), "user_b": ("b@example.test", {})},
        {"user_a": [_membership("org_a", A_TENANT)]},
    )
    _serve(monkeypatch, clerk)
    assert preflight.main([]) == preflight.NEEDS_B_ORGANIZATION


def test_a_jwks_with_private_material_is_never_written(
    monkeypatch: pytest.MonkeyPatch, clerk_env: Path
) -> None:
    clerk = _ready_clerk()
    clerk.jwks = {"keys": [dict(KEY, d="secret")]}
    _serve(monkeypatch, clerk)
    assert preflight.main(["--export-github-env"]) == preflight.FAILED
    assert not (clerk_env / "clerk-jwks.json").exists()


def test_an_a_in_another_tenant_than_the_seed_fails(
    monkeypatch: pytest.MonkeyPatch, clerk_env: Path
) -> None:
    clerk = _ready_clerk()
    clerk.memberships["user_a"] = [_membership("org_a", B_TENANT.replace("a114", "a999"))]
    _serve(monkeypatch, clerk)
    assert preflight.main(["--export-github-env"]) == preflight.FAILED


@pytest.mark.parametrize(
    ("env", "value"),
    [
        ("CLERK_SECRET_KEY", ""),
        ("INTEGRAL_CLERK_DEV_B_EMAIL", ""),
        ("INTEGRAL_CLERK_DEV_B_EMAIL", "A@example.test"),
        ("CLERK_SECRET_KEY", "sk_live_x"),
    ],
)
def test_the_preflight_refuses_missing_equal_or_production_inputs(
    monkeypatch: pytest.MonkeyPatch, clerk_env: Path, env: str, value: str
) -> None:
    monkeypatch.setenv(env, value)
    _serve(monkeypatch, _ready_clerk())
    assert preflight.main([]) == preflight.FAILED


# ── discovery ────────────────────────────────────────────────────────────────────────────────────────────────
def _discover(
    monkeypatch: pytest.MonkeyPatch, clerk: FakeClerk, capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict]:
    _serve(monkeypatch, clerk)
    code = discovery.main()
    return code, json.loads(capsys.readouterr().out)


def test_discovery_reads_everything_and_reports_unmarked_accounts_by_pseudonym(
    monkeypatch: pytest.MonkeyPatch, clerk_env: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    clerk = FakeClerk(
        {
            "user_a": ("a@example.test", {}),
            "old_1": ("old1@real.example", {}),
            "old_2": ("old2@real.example", {}),
        },
        {"user_a": [_membership("org_a", A_TENANT)]},
    )
    code, receipt = _discover(monkeypatch, clerk, capsys)
    assert code == 0
    assert receipt["inventory"] == {
        "complete": True,
        "users_listed": 3,
        "users_counted_by_clerk": 3,
    }
    assert receipt["outcome"] == "INVENTORY_INCOMPLETE"
    assert len(receipt["unmarked_pseudonyms"]) == 2
    assert "real.example" not in json.dumps(receipt)
    assert set(clerk.methods) == {"GET"}


def test_discovery_finds_a_marked_synthetic_candidate(
    monkeypatch: pytest.MonkeyPatch, clerk_env: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    clerk = FakeClerk(
        {
            "user_a": ("a@example.test", {}),
            "cand": ("c@example.test", {"public_metadata": {"c2pro_synthetic": True}}),
        },
        {"user_a": [_membership("org_a", A_TENANT)], "cand": [_membership("org_b", B_TENANT)]},
    )
    code, receipt = _discover(monkeypatch, clerk, capsys)
    assert code == 0
    assert receipt["outcome"] == "DEV_B_CANDIDATE_FOUND"
    assert receipt["candidates"][0]["reason"] == "VALID"


def test_discovery_with_only_a_concludes_that_creation_is_required(
    monkeypatch: pytest.MonkeyPatch, clerk_env: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    clerk = FakeClerk(
        {"user_a": ("a@example.test", {})}, {"user_a": [_membership("org_a", A_TENANT)]}
    )
    code, receipt = _discover(monkeypatch, clerk, capsys)
    assert code == 0
    assert receipt["outcome"] == "DEV_B_CREATION_REQUIRED"


def test_discovery_is_incomplete_when_clerks_count_disagrees(
    monkeypatch: pytest.MonkeyPatch, clerk_env: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    clerk = FakeClerk({"user_a": ("a@example.test", {})}, {})
    original = clerk.handler

    def lying(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/users/count"):
            return httpx.Response(200, json={"total_count": 9})
        return original(request)

    clerk.handler = lying  # type: ignore[method-assign]
    code, receipt = _discover(monkeypatch, clerk, capsys)
    assert code == 1
    assert receipt["outcome"] == "INVENTORY_INCOMPLETE"


def test_discovery_reports_incomplete_when_clerk_answers_an_error(
    monkeypatch: pytest.MonkeyPatch, clerk_env: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _serve(monkeypatch, FakeClerk({}, {}))
    monkeypatch.setattr(
        discovery.ReadOnlyClerk,
        "get",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    assert discovery.main() == 1
    assert json.loads(capsys.readouterr().out)["verdict"] == "INVENTORY_INCOMPLETE"


@pytest.mark.parametrize("secret", ["", "sk_live_x"])
def test_discovery_refuses_a_missing_or_production_key(
    monkeypatch: pytest.MonkeyPatch, clerk_env: Path, secret: str
) -> None:
    monkeypatch.setenv("CLERK_SECRET_KEY", secret)
    assert discovery.main() == 1


def test_the_read_only_client_refuses_any_other_method() -> None:
    client = discovery.ReadOnlyClerk(
        REAL_CLIENT(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))),
        "https://x",
    )
    with pytest.raises(RuntimeError, match="read-only"):
        client.request("POST")


# ── verifier ─────────────────────────────────────────────────────────────────────────────────────────────────
def _verifier_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, browser: dict) -> None:
    manifest = tmp_path / "integral-browser-manifest.json"
    manifest.write_text(json.dumps(browser))
    monkeypatch.setattr(verifier, "BROWSER_MANIFEST", manifest)
    monkeypatch.setattr(verifier, "PROVIDER_RECEIPT", tmp_path / "integral-provider-receipt.json")


def test_the_verifier_writes_the_manifest_to_stdout_and_exits_zero_for_an_honest_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    facts, browser, expect = _world()
    _verifier_files(monkeypatch, tmp_path, browser)
    (tmp_path / "integral-provider-receipt.json").write_text(
        json.dumps({"worker_provider_successes": 3})
    )
    monkeypatch.setenv("DATABASE_URL", "postgresql://u@h/d")
    monkeypatch.setenv("GITHUB_SHA", "c" * 40)
    for name, value in (
        ("CLERK_E2E_USER_ID", expect.clerk_user_a),
        ("CLERK_E2E_ORG_ID", expect.clerk_org_a),
        ("TENANT_B_CLERK_E2E_USER_ID", expect.clerk_user_b),
        ("TENANT_B_CLERK_E2E_ORG_ID", expect.clerk_org_b),
        ("E2E_EXPECTED_TENANT_ID", expect.tenant_a),
        ("TENANT_B_E2E_EXPECTED_TENANT_ID", expect.tenant_b),
    ):
        monkeypatch.setenv(name, value)

    async def fake_collect(*_args: Any) -> Any:
        return facts

    monkeypatch.setattr(verifier, "_collect_facts", fake_collect)
    assert verifier.main() == 0
    manifest = json.loads(capsys.readouterr().out)
    assert manifest["verdict"] == "UAT_REAL_COMPLETE"
    assert manifest["candidate_sha"] == "c" * 40


def test_the_verifier_exits_nonzero_when_postgres_disagrees(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    facts, browser, _ = _world()
    facts.artifacts[3]["trust_state"] = "trusted"
    _verifier_files(monkeypatch, tmp_path, browser)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u@h/d")

    async def fake_collect(*_args: Any) -> Any:
        return facts

    monkeypatch.setattr(verifier, "_collect_facts", fake_collect)
    assert verifier.main() == 1
    assert json.loads(capsys.readouterr().out)["verdict"] == "FAILED"


def test_the_verifier_stops_when_the_browser_recorded_no_project(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _verifier_files(monkeypatch, tmp_path, {"stages": []})
    monkeypatch.setenv("DATABASE_URL", "postgresql://u@h/d")
    assert verifier.main() == 1


def test_the_verifier_treats_a_missing_receipt_file_as_empty(tmp_path: Path) -> None:
    assert verifier._read_json(tmp_path / "absent.json") == {}


# ── runtime receipt ──────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(("matches", "code"), [(True, 0), (False, 1)])
def test_the_runtime_receipt_is_written_at_a_fixed_place_and_exits_by_its_verdict(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, matches: bool, code: int
) -> None:
    monkeypatch.setattr(receipt_script, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(
        receipt_script,
        "build_receipt",
        lambda **_k: {"process_found": True, "cwd_inside_workspace": matches, "matches": matches},
    )
    monkeypatch.setattr(
        "sys.argv",
        ["x", "--role", "backend", "--process-pattern", "uvicorn", "--expected-sha", "a" * 40],
    )
    assert receipt_script.main() == code
    assert (
        json.loads((tmp_path / "integral-runtime-backend.json").read_text())["matches"] is matches
    )


def test_the_runtime_receipt_waits_for_a_late_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(receipt_script, "REPORT_DIR", tmp_path)
    answers = iter(
        [
            {"process_found": False, "matches": False},
            {"process_found": True, "cwd_inside_workspace": True, "matches": True},
        ]
    )
    monkeypatch.setattr(receipt_script, "build_receipt", lambda **_k: next(answers))
    monkeypatch.setattr(receipt_script.time, "sleep", lambda _s: None)
    monkeypatch.setattr(
        "sys.argv",
        [
            "x",
            "--role",
            "frontend",
            "--process-pattern",
            "next dev",
            "--expected-sha",
            "a" * 40,
            "--wait-seconds",
            "30",
        ],
    )
    assert receipt_script.main() == 0


def test_find_pids_ignores_unreadable_entries(tmp_path: Path) -> None:
    proc = tmp_path / "proc"
    (proc / "7").mkdir(parents=True)  # a numeric entry without a cmdline
    (proc / "8").mkdir()
    (proc / "8" / "cmdline").write_bytes(b"uvicorn\0src.main:app")
    assert receipt_script.find_pids("uvicorn", proc) == [8]
