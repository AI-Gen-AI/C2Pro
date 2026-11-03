"""Owner session support: stable local identity and the isolation guard. The database work is covered by the grant step's own PG tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts import owner_session_support as s  # noqa: E402


def test_the_local_row_of_a_clerk_user_is_stable() -> None:
    assert s.owner_user_id("user_abc") == s.owner_user_id("user_abc") != s.owner_user_id("user_abd")


def test_the_email_is_only_fingerprinted() -> None:
    assert s.fingerprint(" A@B.com ") == s.fingerprint("a@b.com") and "a@b.com" not in s.fingerprint("a@b.com")


async def test_the_seed_refuses_a_non_test_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(Exception):  # noqa: B017 - the isolation guard of the grant step, whatever its exact type
        await s.seed("a@b.com", "user_abc")
