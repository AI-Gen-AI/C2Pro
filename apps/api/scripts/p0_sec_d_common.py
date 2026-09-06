"""Shared helpers for the P0-SEC-D function-privilege hardening tooling.

The gate needs the exact ``CREATE FUNCTION`` text for ``public.
handle_new_user()`` as committed in the Supabase init migration, and the
exact ``REVOKE`` text from the P0-SEC-D fix migration, so the gate proves
something about the real committed SQL rather than a hand-copied
approximation that could silently drift from it.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

INIT_SCHEMA_PATH = REPO_ROOT / "supabase/migrations/20260113133853_init_schema.sql"
FIX_MIGRATION_PATH = (
    REPO_ROOT / "supabase/migrations/20260906000100_p0_sec_d_function_privileges.sql"
)
FIXTURE_PATH = REPO_ROOT / "apps/api/tests/security/fixtures/p0_sec_d_prestate.sql"

_HANDLE_NEW_USER_START = "CREATE OR REPLACE FUNCTION public.handle_new_user()"
_TRIGGER_START = "CREATE TRIGGER on_auth_user_created"


def extract_handle_new_user_ddl() -> str:
    """Return the exact ``CREATE FUNCTION public.handle_new_user()`` statement,

    followed by the ``on_auth_user_created`` trigger that wires it to
    ``auth.users``. Extracted from the committed init-schema migration by
    locating each header and its terminator -- the same statements Supabase
    actually applies, not a re-typed copy.
    """
    text = INIT_SCHEMA_PATH.read_text(encoding="utf-8")

    fn_start = text.index(_HANDLE_NEW_USER_START)
    fn_end = text.index("$$;", fn_start) + len("$$;")

    trig_start = text.index(_TRIGGER_START, fn_end)
    trig_end = text.index(";", trig_start) + len(";")

    return text[fn_start:fn_end] + "\n\n" + text[trig_start:trig_end]


def fix_migration_sql() -> str:
    """Return the full P0-SEC-D fix migration text."""
    return FIX_MIGRATION_PATH.read_text(encoding="utf-8")
