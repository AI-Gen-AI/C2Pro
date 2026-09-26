"""Scope validation regression tests for supabase_security_lint.run().

RED against HEAD 0054f665a0afe610379d9985c212e421e31a8337:

  Finding: run(dsn, scope=...) derives run_a and run_b from membership
  in _SCOPE_P0_SEC_A / _SCOPE_P0_SEC_B.  An unknown scope (e.g. "p0_sec_aa")
  is not a member of either frozenset, so both flags are False, no security
  checks execute, and the function reaches:

      PASSED: no blocking violations

  with return code 0 — a fail-open gate.

  This set of tests proves that property is invalid and verifies the fix.

RED tests (fail before fix, pass after):
  A. unknown scope cannot silently execute zero checks
  B. None remains a valid global scope
  C. "p0_sec_a" remains valid
  D. "p0_sec_b" remains valid
  E. existing gate-composition invariants (_SCOPE_P0_SEC_A, _SCOPE_P0_SEC_B) unchanged
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import supabase_security_lint as _lint  # noqa: E402

pytestmark = pytest.mark.security


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_mock_conn() -> MagicMock:
    """Return a mock connection that succeeds and executes zero real queries."""
    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = []
    mock_cur.fetchone.return_value = (0,)

    mock_cursor_cm = MagicMock()
    mock_cursor_cm.__enter__ = MagicMock(return_value=mock_cur)
    mock_cursor_cm.__exit__ = MagicMock(return_value=False)

    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor_cm
    return mock_conn


def _connect_target() -> str:
    """Return the fully-qualified name of the connect function to patch."""
    try:
        import psycopg  # noqa: F401

        return "psycopg.connect"
    except ImportError:
        return "psycopg2.connect"


# ── A. unknown scope must fail closed ────────────────────────────────────────


def test_valid_scopes_constant_is_defined() -> None:
    """_VALID_SCOPES must exist so that scope validation is possible at all.

    RED proof: _VALID_SCOPES is absent from the module.  Without it, run() has
    no explicit guard against unknown scopes.  An unknown scope such as
    'p0_sec_aa' evaluates:

        run_a = 'p0_sec_aa' in _SCOPE_P0_SEC_A  → False
        run_b = 'p0_sec_aa' in _SCOPE_P0_SEC_B  → False

    making zero security checks execute before reaching "PASSED".
    """
    assert hasattr(_lint, "_VALID_SCOPES"), (
        "_VALID_SCOPES is not defined — run() has no explicit scope validation. "
        "Proof that bug exists: scope='p0_sec_aa' → "
        f"run_a={'p0_sec_aa' in _lint._SCOPE_P0_SEC_A}, "
        f"run_b={'p0_sec_aa' in _lint._SCOPE_P0_SEC_B} → "
        "zero checks execute → PASSED (fail-open)"
    )


def test_valid_scopes_is_exactly_correct_frozenset() -> None:
    """_VALID_SCOPES must be exactly frozenset({None, 'p0_sec_a', 'p0_sec_b', 'p0_sec_d'}).

    RED proof: _VALID_SCOPES is not defined → AttributeError.
    """
    expected: frozenset[str | None] = frozenset(
        {None, "p0_sec_a", "p0_sec_b", "p0_sec_d"}
    )
    actual = getattr(_lint, "_VALID_SCOPES", None)
    assert actual == expected, (
        f"_VALID_SCOPES={actual!r} must be exactly {expected!r}; "
        "every valid scope must be listed and nothing else accepted"
    )


def test_unknown_scope_not_in_valid_scopes() -> None:
    """'p0_sec_aa' must NOT appear in _VALID_SCOPES.

    RED proof: _VALID_SCOPES is not defined → assertion fails (actual is None).
    """
    actual = getattr(_lint, "_VALID_SCOPES", None)
    assert actual is not None, "_VALID_SCOPES is not defined — validation contract is missing"
    assert "p0_sec_aa" not in actual, (
        "unknown scope 'p0_sec_aa' is accepted — validation contract is wrong"
    )


def test_unknown_scope_silently_returns_pass_without_fix() -> None:
    """Before fix: mocked DB + unknown scope returns 0 (fail-open).
    After fix: scope validation fires before any DB work and returns non-zero.

    This is the key behavioral RED proof: with a DB connection that succeeds,
    the current code runs zero checks and returns 0 for any unknown scope.

    RED: rc == 0 → assert rc != 0 fails.
    GREEN: scope validation returns 1 before DB is touched.
    """
    mock_conn = _make_mock_conn()
    with patch(_connect_target(), return_value=mock_conn):
        rc = _lint.run("postgresql://localhost/test", scope="p0_sec_aa")

    assert rc != 0, (
        f"unknown scope 'p0_sec_aa' silently returned rc={rc} (PASS) — "
        "fail-open: zero security checks executed without error"
    )


# ── B–D. valid scopes remain valid after the fix ─────────────────────────────


def test_none_scope_is_in_valid_scopes() -> None:
    """None (global lint — all controls) must remain a valid scope.

    RED proof: _VALID_SCOPES not defined → actual is None → assertion fails.
    """
    actual = getattr(_lint, "_VALID_SCOPES", None)
    assert actual is not None, "_VALID_SCOPES is not defined — global lint scope would be broken"
    assert None in actual, (
        "None is not in _VALID_SCOPES — global lint scope would be broken by the fix"
    )


def test_p0_sec_a_scope_is_in_valid_scopes() -> None:
    """'p0_sec_a' must remain a valid scope.

    RED proof: _VALID_SCOPES not defined → actual is None → assertion fails.
    """
    actual = getattr(_lint, "_VALID_SCOPES", None)
    assert actual is not None, "_VALID_SCOPES is not defined — P0-SEC-A gate scope would be broken"
    assert "p0_sec_a" in actual, (
        "'p0_sec_a' is not in _VALID_SCOPES — P0-SEC-A gate scope would be broken"
    )


def test_p0_sec_b_scope_is_in_valid_scopes() -> None:
    """'p0_sec_b' must remain a valid scope.

    RED proof: _VALID_SCOPES not defined → actual is None → assertion fails.
    """
    actual = getattr(_lint, "_VALID_SCOPES", None)
    assert actual is not None, "_VALID_SCOPES is not defined — P0-SEC-B gate scope would be broken"
    assert "p0_sec_b" in actual, (
        "'p0_sec_b' is not in _VALID_SCOPES — P0-SEC-B gate scope would be broken"
    )


def test_p0_sec_d_scope_is_in_valid_scopes() -> None:
    """'p0_sec_d' must be a valid scope."""
    actual = getattr(_lint, "_VALID_SCOPES", None)
    assert actual is not None, "_VALID_SCOPES is not defined — P0-SEC-D gate scope would be broken"
    assert "p0_sec_d" in actual, (
        "'p0_sec_d' is not in _VALID_SCOPES — P0-SEC-D gate scope would be broken"
    )


# ── E. existing gate-composition invariants must be unchanged ─────────────────


def test_scope_p0_sec_a_membership_unchanged() -> None:
    """_SCOPE_P0_SEC_A must still be frozenset({'p0_sec_a', None}).

    This invariant was established by the gate-composition fix (commit aab4fbca).
    The scope-validation fix must not alter it.
    """
    assert frozenset({"p0_sec_a", None}) == _lint._SCOPE_P0_SEC_A, (
        f"_SCOPE_P0_SEC_A changed: {_lint._SCOPE_P0_SEC_A!r}"
    )


def test_scope_p0_sec_b_membership_unchanged() -> None:
    """_SCOPE_P0_SEC_B must still be frozenset({'p0_sec_b', None}).

    This invariant was established by the gate-composition fix (commit aab4fbca).
    The scope-validation fix must not alter it.
    """
    assert frozenset({"p0_sec_b", None}) == _lint._SCOPE_P0_SEC_B, (
        f"_SCOPE_P0_SEC_B changed: {_lint._SCOPE_P0_SEC_B!r}"
    )


def test_scope_p0_sec_d_membership_is_correct() -> None:
    """_SCOPE_P0_SEC_D must be frozenset({'p0_sec_d', None})."""
    assert frozenset({"p0_sec_d", None}) == _lint._SCOPE_P0_SEC_D, (
        f"_SCOPE_P0_SEC_D is wrong: {_lint._SCOPE_P0_SEC_D!r}"
    )


def test_p0_sec_d_scope_dispatches_to_its_own_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """scope='p0_sec_d' must invoke _check_p0_sec_d and nothing else."""
    calls: list[str] = []
    monkeypatch.setattr(_lint, "_check_p0_sec_a", lambda *a, **k: calls.append("a"))
    monkeypatch.setattr(_lint, "_check_p0_sec_b", lambda *a, **k: calls.append("b"))
    monkeypatch.setattr(_lint, "_check_p0_sec_d", lambda *a, **k: calls.append("d"))

    mock_conn = _make_mock_conn()
    with patch(_connect_target(), return_value=mock_conn):
        _lint.run("postgresql://unused/unused", scope="p0_sec_d")

    assert calls == ["d"], f"expected only the P0-SEC-D check to run, got {calls!r}"
