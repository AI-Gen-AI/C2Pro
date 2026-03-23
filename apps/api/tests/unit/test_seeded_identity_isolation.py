"""TS-OPS-SEED-ISO-001

Regression checks for seeded identity isolation safeguards.
"""

from __future__ import annotations

import pytest

from tests.support.seeded_identity_guard import assert_seeded_identity_isolation_safe


def test_seeded_identity_guard_rejects_non_test_database() -> None:
    with pytest.raises(RuntimeError, match="Seeded auth identities may only run against test databases"):
        assert_seeded_identity_isolation_safe("postgresql://app:secret@db.example.com/c2pro_prod")


def test_seeded_identity_guard_allows_test_database() -> None:
    assert_seeded_identity_isolation_safe("postgresql://postgres:postgres@localhost:5433/c2pro_test")
