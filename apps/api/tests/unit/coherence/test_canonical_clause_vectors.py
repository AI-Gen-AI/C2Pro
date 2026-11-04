"""Canonical clause embeddings are revision-aware, tenant-scoped and opt-in."""

from __future__ import annotations

import hashlib
import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.coherence.application.canonical_clause_vectors import (
    _source_metadata,
    index_current_clause_vectors,
)


def _source(*, revision=None, document=None, existing=None):
    return {
        "clause_id": str(uuid4()),
        "full_text": "Supplier must provide certified transformers under Annex A.",
        "revision_id": str(revision or uuid4()),
        "document_id": str(document or uuid4()),
        "document_type": "contract",
        "source_page": 4,
        "text_start_offset": 12,
        "text_end_offset": 71,
        "existing_metadata": existing,
    }


def _db_with_sources(sources, *, insert_id=True):
    db = AsyncMock()
    db.scalar.return_value = True
    first = MagicMock()
    result = MagicMock()
    result.mappings.return_value.all.return_value = sources
    insert = MagicMock()
    insert.scalar_one_or_none.return_value = uuid4() if insert_id else None
    db.execute.side_effect = [first, result] + ([insert] * len(sources))
    return db


@pytest.mark.asyncio
async def test_indexes_one_valid_clause_with_source_provenance_and_no_commit():
    source = _source()
    db = _db_with_sources([source])
    embed = AsyncMock(return_value=[[0.1] * 1536])
    result = await index_current_clause_vectors(
        db=db, tenant_id=uuid4(), project_id=uuid4(),
        clause_ids=[source["clause_id"]], embed=embed,
    )
    assert result["state"] == "CURRENT"
    assert result["indexed"] == 1
    assert result["embedding_model"] == "text-embedding-3-small"
    embed.assert_awaited_once_with([source["full_text"]])
    assert db.execute.await_count == 3
    params = db.execute.await_args.args[1]
    metadata = json.loads(params["metadata"])
    assert metadata["revision_id"] == source["revision_id"]
    assert metadata["document_id"] == source["document_id"]
    assert metadata["source_page"] == 4
    assert metadata["text_sha256"] == hashlib.sha256(
        source["full_text"].encode("utf-8")
    ).hexdigest()
    db.commit.assert_not_awaited()
    sql = str(db.execute.await_args.args[0])
    assert "c.revision_id = cur.revision_id" in sql
    assert "cur.trusted" in sql
    assert "cur.canonical" in sql
    assert "ON CONFLICT" in sql
    assert "clause_embeddings.document_id = EXCLUDED.document_id" in sql


@pytest.mark.asyncio
async def test_skips_matching_current_clause_without_provider_call():
    source = _source()
    source["existing_metadata"] = _source_metadata(source)
    db = _db_with_sources([source])
    embed = AsyncMock()
    result = await index_current_clause_vectors(
        db=db, tenant_id=uuid4(), project_id=uuid4(),
        clause_ids=[source["clause_id"]], embed=embed,
    )
    assert result["indexed"] == 0
    assert result["unchanged"] == 1
    db.execute.assert_awaited()
    assert db.execute.await_count == 2
    embed.assert_not_awaited()


@pytest.mark.asyncio
async def test_foreign_project_is_rejected_before_sql_writes_or_embedding():
    db = AsyncMock()
    db.scalar.return_value = False
    embed = AsyncMock()
    with pytest.raises(PermissionError, match="FOREIGN_PROJECT"):
        await index_current_clause_vectors(
            db=db, tenant_id=uuid4(), project_id=uuid4(),
            clause_ids=[str(uuid4())], embed=embed,
        )
    db.execute.assert_not_awaited()
    embed.assert_not_awaited()


@pytest.mark.asyncio
async def test_wrong_dimensions_never_writes_embedding():
    source = _source()
    db = _db_with_sources([source])
    embed = AsyncMock(return_value=[[0.2] * 12])
    with pytest.raises(ValueError, match="WRONG_DIMENSIONS"):
        await index_current_clause_vectors(
            db=db, tenant_id=uuid4(), project_id=uuid4(),
            clause_ids=[source["clause_id"]], embed=embed,
        )
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_failed_source_recheck_is_not_reported_as_indexed():
    source = _source()
    db = _db_with_sources([source], insert_id=False)
    embed = AsyncMock(return_value=[[0.1] * 1536])
    with pytest.raises(RuntimeError, match="SOURCE_CHANGED"):
        await index_current_clause_vectors(
            db=db, tenant_id=uuid4(), project_id=uuid4(),
            clause_ids=[source["clause_id"]], embed=embed,
        )
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_capped_candidates_are_explicitly_partial():
    a, b = _source(), _source()
    db = _db_with_sources([a, b])
    # No synthetic LLM/provider call necessary: returned extra row is omitted.
    embed = AsyncMock(return_value=[[0.1] * 1536])
    result = await index_current_clause_vectors(
        db=db, tenant_id=uuid4(), project_id=uuid4(),
        clause_ids=[a["clause_id"], b["clause_id"]],
        max_units=1, embed=embed,
    )
    assert result["state"] == "PARTIAL"
    assert result["additional_units_unassessed"] is True
    assert result["indexed"] == 1


def test_select_filters_tenant_revision_source_and_technical_trust():
    from src.coherence.application.canonical_clause_vectors import (
        _CURRENT_CLAUSE_SOURCES,
    )
    query = str(_CURRENT_CLAUSE_SOURCES)
    assert "c.tenant_id = CAST(:tenant_id AS uuid)" in query
    assert "c.project_id = CAST(:project_id AS uuid)" in query
    assert "c.revision_id = cur.revision_id" in query
    assert "cur.canonical" in query
    assert "cur.trusted" in query
    assert "ce.metadata AS existing_metadata" in query


def test_pgvector_pairs_require_revision_and_same_tenant():
    # Static contract: N8 must not call the old revision-unaware SQL function.
    from pathlib import Path

    root = Path(__file__).resolve().parents[4]
    source = (
        root
        / "src"
        / "coherence"
        / "adapters"
        / "persistence"
        / "pgvector_embedding_repository.py"
    ).read_text(encoding="utf-8")
    method = source.split("async def find_cross_document_pairs(", 1)[1].split(
        "async def get_embedding(", 1
    )[0]
    assert "FROM public.clause_embeddings AS e1" in method
    assert "e1.tenant_id = CAST(:tenant_id AS uuid)" in method
    assert "c1.revision_id = cur1.revision_id" in method
    assert "c2.revision_id = cur2.revision_id" in method
    assert "cur1.canonical" in method
    assert "cur2.trusted" in method
    assert "find_cross_document_pairs(" not in method.split("stmt = sql_text(", 1)[1]
