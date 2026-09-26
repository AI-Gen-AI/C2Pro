"""PJ-01: the P0c browser fixture persists through a real repository append.

Moved from tests/unit/temporal/test_p0c_browser_fixture.py: this test needs a real `db`
(live PostgreSQL session) to prove the fixture writes append-only events and returns a
faithful manifest. The Unit Tests CI job runs `pytest tests/unit/ -m "not integration"`
with no database service, so a DB-dependent test never belonged there -- it silently
tried to reach PostgreSQL on localhost:5433 and failed with a connection error rather
than a real assertion failure. The two pure-logic tests in the original file (fixture
shape, manifest-writer JSON serialization) need no database and stay in tests/unit/.
"""

from __future__ import annotations

import pytest

from tests.e2e_seed.p0c_temporal import seed_p0c_browser_fixture


@pytest.mark.asyncio
async def test_fixture_persists_only_append_only_events_and_returns_browser_manifest(db) -> None:  # noqa: ANN001
    """Removing a real repository append or exposing mutable evidence must fail fixture setup."""
    manifest = await seed_p0c_browser_fixture(db)

    assert manifest["project_id"]
    assert manifest["document_id"]
    assert manifest["revisions"]["A"]["blob_hash"] != manifest["revisions"]["B"]["blob_hash"]
    assert manifest["events"]["B"]["change_cause"] == "BUSINESS_STATE_CHANGED"
    assert manifest["events"]["C"]["change_cause"] == "NEWLY_DISCOVERED"
    assert manifest["events"]["D"]["change_cause"] is None
