"""D1: test the existing shared WBS authority gate, not a duplicate resolver.

These are isolated unit-level failure-path tests. Real database baseline/tenant
isolation remains a separate integration acceptance requirement.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.wbs.adapters.persistence import link_authority as gate
from src.wbs.domain.governance import resolve_authority, BaselineRef


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)


class _Session:
    def __init__(self, rows_by_query):
        self.rows_by_query = rows_by_query
        self.calls = []

    async def execute(self, query, params):
        sql = str(query)
        self.calls.append((sql, params))
        if "JOIN wbs_nodes" in sql:
            return _Rows([(node,) for node in self.rows_by_query.get("current", [])])
        if "SELECT DISTINCT node_id FROM wbs_baseline_nodes" in sql:
            return _Rows([(node,) for node in self.rows_by_query.get("historical", [])])
        if "SELECT DISTINCT node_id FROM wbs_change_set_nodes" in sql:
            return _Rows([(node,) for node in self.rows_by_query.get("candidate", [])])
        raise AssertionError(f"Unexpected authority query: {sql}")


def _approved():
    return resolve_authority(
        current_baseline=BaselineRef(
            baseline_id=uuid4(), baseline_no=1, tree_digest="sha256:" + "a" * 64,
            applied_at=datetime.now(UTC),
        ),
        live_node_count=1, open_change_sets=0,
    )


@pytest.mark.asyncio
async def test_missing_or_foreign_project_fails_closed(monkeypatch):
    async def absent(*_args):
        return None

    monkeypatch.setattr(gate, "_authority_under_lock", absent)
    with pytest.raises(gate.WBSNodeNotCurrentBaselineError):
        await gate.require_linkable_wbs_nodes(
            _Session({}), tenant_id=uuid4(), project_id=uuid4(), node_ids={uuid4()}
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy_count,drafts", [(0, 0), (0, 1), (2, 0)])
async def test_no_approved_baseline_refuses_new_mapping(monkeypatch, legacy_count, drafts):
    authority = resolve_authority(
        current_baseline=None, live_node_count=legacy_count, open_change_sets=drafts
    )

    async def scope(*_args):
        return authority

    monkeypatch.setattr(gate, "_authority_under_lock", scope)
    with pytest.raises(gate.WBSNotApprovedError):
        await gate.require_linkable_wbs_nodes(
            _Session({}), tenant_id=uuid4(), project_id=uuid4(), node_ids={uuid4()}
        )


@pytest.mark.asyncio
async def test_current_approved_node_resolves_under_exact_scope(monkeypatch):
    authority = _approved()

    async def scope(*_args):
        return authority

    monkeypatch.setattr(gate, "_authority_under_lock", scope)
    tenant, project, node = uuid4(), uuid4(), uuid4()
    session = _Session({"current": [node]})
    result = await gate.require_linkable_wbs_nodes(
        session, tenant_id=tenant, project_id=project, node_ids={node}
    )
    assert result.baseline_id == authority.baseline_id
    assert session.calls[0][1] == {
        "b": authority.baseline_id, "p": project, "t": tenant, "ids": [node]
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("classification", ["retired", "candidate", "foreign"])
async def test_unapproved_node_never_falls_back_to_code(monkeypatch, classification):
    authority = _approved()

    async def scope(*_args):
        return authority

    monkeypatch.setattr(gate, "_authority_under_lock", scope)
    node = uuid4()
    rows = {
        "historical": [node] if classification == "retired" else [],
        "candidate": [node] if classification == "candidate" else [],
    }
    error = (
        gate.WBSCandidateNotCanonicalError
        if classification == "candidate"
        else gate.WBSNodeNotCurrentBaselineError
    )
    with pytest.raises(error):
        await gate.require_linkable_wbs_nodes(
            _Session(rows), tenant_id=uuid4(), project_id=uuid4(), node_ids={node}
        )
