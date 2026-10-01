"""#727 async-runtime schema readiness contract."""

from pathlib import Path

import pytest

from scripts.wait_for_schema import expected_heads, schema_ready

API_ROOT = Path(__file__).resolve().parents[2]


def test_repository_has_exactly_one_alembic_head() -> None:
    heads = expected_heads(API_ROOT)
    assert len(heads) == 1


def test_schema_ready_only_when_database_equals_repository_head() -> None:
    assert schema_ready(expected={"head-2"}, current={"head-2"}) is True
    assert schema_ready(expected={"head-2"}, current={"head-1"}) is False
    assert schema_ready(expected={"head-2"}, current=set()) is False
    assert schema_ready(expected={"head-2"}, current={"head-3"}) is False


def test_database_multi_head_fails_closed() -> None:
    with pytest.raises(RuntimeError, match="database has 2 Alembic heads"):
        schema_ready(expected={"head-2"}, current={"head-1", "head-2"})


def test_repository_multi_head_fails_closed() -> None:
    with pytest.raises(RuntimeError, match="exactly one head"):
        schema_ready(expected={"head-a", "head-b"}, current={"head-a"})
