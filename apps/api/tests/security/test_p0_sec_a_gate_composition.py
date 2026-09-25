"""Gate composition contract: P0-SEC-A gate must only validate P0-SEC-A invariants.

GATE_COMPOSITION_REGRESSION root cause (CI run 33967746112):
  After the P0-SEC-B lint enhancement, the global supabase_security_lint.run()
  also detects COALESCE fail-open policies. The P0-SEC-A isolated fixture
  intentionally contains COALESCE prestate (P0-SEC-B scope, not P0-SEC-A scope).
  Calling global lint inside the P0-SEC-A gate's 'after upgrade' phase produces
  8 P0-SEC-B blockers, causing a false failure in the A gate.

Required architecture:
  P0-SEC-A gate  -> run(dsn, scope="p0_sec_a") — only A-owned invariants
  P0-SEC-B gate  -> run(dsn) or run(dsn, scope="p0_sec_b") — B invariants
  Global lint    -> run(dsn) validates ALL active controls (unchanged)

RED tests (will FAIL before the fix):
  1. run() accepts scope parameter
  2. _SCOPE_P0_SEC_A defined and correct
  3. _SCOPE_P0_SEC_B defined and correct
  4. p0_sec_a_gate._lint_passes uses scoped call

GREEN invariants (already pass — documenting the contract):
  5. P0-SEC-A fixture contains COALESCE prestate (proves the B scope is real)
  6. Global lint (scope=None) retains Q_BLOCKING_FAIL_OPEN as BLOCKING
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.security

REPO_ROOT = Path(__file__).resolve().parents[4]
GATE = REPO_ROOT / "apps/api/scripts/p0_sec_a_gate.py"
FIXTURE = REPO_ROOT / "apps/api/tests/security/fixtures/p0_sec_a_prestate.sql"

sys.path.insert(0, str(REPO_ROOT / "apps/api/scripts"))
import supabase_security_lint as _lint  # noqa: E402

# ── RED: structural tests that FAIL before the fix ───────────────────────────


def test_lint_run_signature_has_scope_parameter() -> None:
    """run() must accept a 'scope' parameter so gates can opt into a subset.

    Without a scope parameter the A gate is forced to use the global linter,
    which causes false failures when P0-SEC-B blockers are legitimately present
    in a P0-SEC-A-only historical fixture.
    """
    sig = inspect.signature(_lint.run)
    assert "scope" in sig.parameters, (
        "supabase_security_lint.run() has no 'scope' parameter. "
        "Add scope: str | None = None to allow gates to validate only their "
        "own control family."
    )


def test_scope_p0_sec_a_defined_and_correct() -> None:
    """_SCOPE_P0_SEC_A must include 'p0_sec_a' and None but not 'p0_sec_b'.

    None = global (runs all checks including A).
    'p0_sec_a' = A-only (runs only A checks).
    'p0_sec_b' must NOT appear so the P0-SEC-A gate never runs B checks.
    """
    assert hasattr(_lint, "_SCOPE_P0_SEC_A"), (
        "_SCOPE_P0_SEC_A not defined on supabase_security_lint. "
        "Add it as a frozenset marking which scope values activate A checks."
    )
    scope_a = _lint._SCOPE_P0_SEC_A
    assert None in scope_a, (
        "None (global) must be in _SCOPE_P0_SEC_A so global run() still "
        "executes A checks."
    )
    assert "p0_sec_a" in scope_a, (
        "'p0_sec_a' must be in _SCOPE_P0_SEC_A."
    )
    assert "p0_sec_b" not in scope_a, (
        "'p0_sec_b' must NOT be in _SCOPE_P0_SEC_A — the A gate must not "
        "run B checks against the A-only fixture."
    )


def test_scope_p0_sec_b_defined_and_correct() -> None:
    """_SCOPE_P0_SEC_B must include 'p0_sec_b' and None but not 'p0_sec_a'.

    None = global (runs all checks including B).
    'p0_sec_b' = B-only (runs only B checks).
    'p0_sec_a' must NOT appear so the P0-SEC-B gate doesn't re-run A checks.
    """
    assert hasattr(_lint, "_SCOPE_P0_SEC_B"), (
        "_SCOPE_P0_SEC_B not defined on supabase_security_lint. "
        "Add it as a frozenset marking which scope values activate B checks."
    )
    scope_b = _lint._SCOPE_P0_SEC_B
    assert None in scope_b, (
        "None (global) must be in _SCOPE_P0_SEC_B so global run() still "
        "executes B checks."
    )
    assert "p0_sec_b" in scope_b, (
        "'p0_sec_b' must be in _SCOPE_P0_SEC_B."
    )
    assert "p0_sec_a" not in scope_b, (
        "'p0_sec_a' must NOT be in _SCOPE_P0_SEC_B — a P0-SEC-A-scoped call "
        "must not execute B checks."
    )


def test_p0_sec_a_gate_lint_passes_uses_scoped_call() -> None:
    """_lint_passes() in p0_sec_a_gate must call _lint.run with scope='p0_sec_a'.

    Calling _lint.run(dsn) (global) inside the A gate causes false failures
    because the A-only fixture legitimately contains P0-SEC-B prestate.
    """
    gate_text = GATE.read_text(encoding="utf-8")
    has_scope = 'scope="p0_sec_a"' in gate_text or "scope='p0_sec_a'" in gate_text
    assert has_scope, (
        "p0_sec_a_gate.py:_lint_passes() must call _lint.run(dsn, scope='p0_sec_a'). "
        "Using the global (unscoped) linter forces the A gate to fail when P0-SEC-B "
        "blockers are legitimately present in the A-only fixture."
    )


# ── GREEN: invariant tests that already pass (contract documentation) ─────────


def test_p0_sec_a_fixture_contains_coalesce_prestate() -> None:
    """P0-SEC-A fixture must contain COALESCE policies — they are P0-SEC-B scope.

    The fixture explicitly reproduces the COALESCE prestate so the A migration
    can prove it does NOT alter B-scope objects. Any P0-SEC-A gate check that
    requires zero COALESCE policies would be testing the wrong scope.
    """
    fixture_text = FIXTURE.read_text(encoding="utf-8")
    assert "COALESCE" in fixture_text, (
        "P0-SEC-A fixture must contain COALESCE policies to prove P0-SEC-A "
        "does not alter P0-SEC-B-scope objects."
    )
    assert "P0-SEC-B" in fixture_text, (
        "P0-SEC-A fixture must document the scope boundary ('P0-SEC-B') to "
        "make clear which objects are out of P0-SEC-A scope."
    )


def test_global_lint_coalesce_detection_remains_blocking() -> None:
    """Q_BLOCKING_FAIL_OPEN must remain on the global linter (scope=None).

    The scope fix must NOT remove COALESCE detection from the global lint path.
    Only the P0-SEC-A-scoped call should skip it.
    """
    assert hasattr(_lint, "Q_BLOCKING_FAIL_OPEN"), (
        "Q_BLOCKING_FAIL_OPEN was removed from supabase_security_lint — "
        "COALESCE detection must remain active for the global (unscoped) linter."
    )
    assert "COALESCE" in _lint.Q_BLOCKING_FAIL_OPEN, (
        "Q_BLOCKING_FAIL_OPEN must still match COALESCE expressions."
    )
