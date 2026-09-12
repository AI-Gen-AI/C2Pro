"""C2.6 -- disposable-harness acceptance (spec section 13.5, H01-H03).

H01 (disposable DB + synthetic restricted LOGIN + real cross-tenant capability
proofs, RE-RUNNING C2.5's authoritative proofs rather than duplicating them)
and H02 (ownership-tracked teardown proof) are implemented in
``apps/api/scripts/c26_platform_operator_gate.py`` -- a self-contained
disposable-database gate, in the same family as ``c25_admin_ops_gate.py`` /
``c2_checkpoint_gate.py``, not a pytest module. This mirrors the codebase's
existing pattern: authoritative real-Postgres proofs live in a standalone
gate script, run as its own CI step, against `P0_SEC_ADMIN_DSN`; pytest
carries the mock-level unit/structural coverage plus any DSN-gated local
convenience tests. See that script's module docstring and the C2.6
specification (docs/C2_6_PLATFORM_OPERATOR_AUTHORIZATION_BOUNDARY.md) section
13.5 for the full H01/H02 proof list it runs: C2.5's re-proven capability/
grant/RLS assertions, then the new N/P/G5/E1/P03 platform-operator proofs
against the real DLQAdminOpsAdapter and require_platform_operator.

H03 (persistent-runtime proof: with no harness or enablement operation
having run, the *persistent* application configuration resolves
ADMIN_OPS_DATABASE_URL / PLATFORM_OPERATOR_ORG_ID to absent) needs no
database at all -- it is a pure Settings() construction check, covered here.
"""

from __future__ import annotations

import pytest

from src.config import Settings
from tests.unit.core.test_config_settings import _set_required_settings_env


def test_h03_persistent_settings_resolve_capability_and_authz_absent_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no harness running and no separate enablement operation having
    occurred, a persistent Settings() construction (mirroring real runtime
    env, not the disposable harness) must resolve ADMIN_OPS_DATABASE_URL and
    PLATFORM_OPERATOR_ORG_ID to absent -- proving C2.6 merge alone enables
    neither the C2.5 capability nor a platform-operator identity (AC13,
    AC16, spec S07)."""
    _set_required_settings_env(monkeypatch)
    monkeypatch.delenv("ADMIN_OPS_DATABASE_URL", raising=False)
    monkeypatch.delenv("PLATFORM_OPERATOR_ORG_ID", raising=False)
    monkeypatch.delenv("PLATFORM_OPERATOR_USER_IDS", raising=False)

    settings = Settings(_env_file=None)

    assert settings.admin_ops_database_url is None
    assert settings.platform_operator_org_id is None
    assert settings.platform_operator_user_ids == []


def test_h03_no_persistent_environment_file_defines_admin_ops_or_platform_operator_config() -> None:
    """Structural guard mirroring S07: no committed environment-configuration
    template in the repository may define ADMIN_OPS_DATABASE_URL or
    PLATFORM_OPERATOR_ORG_ID as a persistent value. Harness-local fixtures
    (c26_platform_operator_gate.py, c25_admin_ops_gate.py) are exempt by
    construction -- they never touch these files; they pass values as
    in-process env/settings mutations scoped to their own execution."""
    import re
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[4]
    forbidden = re.compile(r"^\s*(ADMIN_OPS_DATABASE_URL|PLATFORM_OPERATOR_ORG_ID)\s*=", re.MULTILINE)

    candidates = [
        repo_root / ".env.example",
        repo_root / "apps" / "api" / ".env.example",
    ]
    deploy_dir = repo_root / "deploy"
    if deploy_dir.is_dir():
        candidates.extend(deploy_dir.glob("*.env"))
    for path in candidates:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        assert not forbidden.search(text), (
            f"{path} defines a persistent ADMIN_OPS_DATABASE_URL or "
            "PLATFORM_OPERATOR_ORG_ID value -- C2.6 merge must not enable "
            "either as a side effect."
        )
