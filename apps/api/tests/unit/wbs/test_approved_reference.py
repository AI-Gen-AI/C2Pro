"""D1 negative tests for strict approved WBS reference resolution."""
from __future__ import annotations

from uuid import uuid4

import pytest

from src.wbs.application.approved_reference import (
    UnapprovedWBSReference,
    resolve_approved_wbs_reference,
)


class _Scalar:
    def __init__(self, code: str | None):
        self.code = code

    def scalar_one_or_none(self) -> str | None:
        return self.code


class _Session:
    def __init__(self, code: str | None):
        self.code = code
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return _Scalar(self.code)


@pytest.mark.asyncio
async def test_explicit_approved_reference_returns_all_original_identities() -> None:
    ids = [uuid4() for _ in range(4)]
    session = _Session("1.1")
    result = await resolve_approved_wbs_reference(
        session, tenant_id=ids[0], project_id=ids[1],
        baseline_id=ids[2], node_id=ids[3],
    )
    assert (result.tenant_id, result.project_id, result.baseline_id, result.node_id) == tuple(ids)
    assert result.code == "1.1"
    compiled = session.statement.compile()\n    values = set(compiled.params.values())\n    assert all(identity in values for identity in ids)\n    assert "human" in values


@pytest.mark.asyncio
async def test_unresolvable_reference_fails_closed() -> None:
    # DB-backed isolation and approved-baseline tests are still required.
    session = _Session(None)
    with pytest.raises(UnapprovedWBSReference, match="approved baseline"):
        await resolve_approved_wbs_reference(
            session, tenant_id=uuid4(), project_id=uuid4(),
            baseline_id=uuid4(), node_id=uuid4(),
        )
