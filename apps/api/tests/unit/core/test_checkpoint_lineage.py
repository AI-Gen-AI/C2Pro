"""Unit coverage for the #758 authority-scoped checkpoint lineage identity.

Pure functions, exercised directly -- no LangGraph runtime, no database -- so
codecov patch coverage reflects this module regardless of which CI job
partitions the DB-backed integration suites (the same reason
test_persist_real_checkpoint_id.py exists).

The behavioural proof that this identity actually isolates a stale processing
attempt lives in
tests/integration/document_flow/test_758_checkpoint_lineage_authority_fence.py,
against real PostgreSQL and a real AsyncPostgresSaver.
"""

from __future__ import annotations

from uuid import uuid4

from src.core import checkpoint_lineage as lineage
from src.core.processing_authority import ProcessingAuthority, ProcessingStage


def _authority(
    *, document_id, generation: int = 1, fence: int = 1
) -> ProcessingAuthority:
    return ProcessingAuthority(
        tenant_id=uuid4(),
        document_id=document_id,
        revision_id=None,
        generation=generation,
        stage=ProcessingStage.ANALYSIS,
        attempt_id=uuid4(),
        owner_token=uuid4(),
        fencing_token=fence,
    )


def test_thread_id_is_deterministic_for_one_attempt() -> None:
    """Same grant -> same thread: the identity is derived, never randomized.

    This is what keeps a redelivery that re-adopts the same grant from
    orphaning its own checkpoint and re-triggering a fresh HITL interrupt.
    """
    document_id = uuid4()
    authority = _authority(document_id=document_id)
    first = lineage.analysis_thread_id(document_id=document_id, authority=authority)
    second = lineage.analysis_thread_id(document_id=document_id, authority=authority)
    assert first == second
    assert str(document_id) in first


def test_every_distinct_attempt_gets_a_distinct_thread() -> None:
    """Takeover, retry and reprocess must not share a lineage."""
    document_id = uuid4()
    threads = {
        lineage.analysis_thread_id(
            document_id=document_id, authority=_authority(document_id=document_id, fence=f)
        )
        for f in (1, 2, 3)
    }
    assert len(threads) == 3

    reprocess = lineage.analysis_thread_id(
        document_id=document_id,
        authority=_authority(document_id=document_id, generation=2, fence=4),
    )
    assert reprocess not in threads


def test_thread_id_fits_the_review_items_column() -> None:
    """review_items.thread_id is String(255); a lineage id must never exceed it."""
    thread = lineage.analysis_thread_id(
        document_id=uuid4(),
        authority=_authority(
            document_id=uuid4(), generation=999_999, fence=9_999_999_999
        ),
    )
    assert len(thread) <= 255


def test_no_authority_falls_back_to_the_legacy_shared_name() -> None:
    """A run with no bound authority keeps the pre-#758 identity exactly.

    Production analysis always runs under an authority, so this is a
    compatibility edge (DB-less tests, any unowned path) -- it must not
    silently change identity for those callers.
    """
    document_id = uuid4()
    thread = lineage.analysis_thread_id(document_id=document_id, authority=None)
    assert thread == lineage.legacy_shared_analysis_thread_id(document_id)
    assert thread == f"document:{document_id}:analysis"


def test_authority_scoped_threads_are_recognised() -> None:
    document_id = uuid4()
    scoped = lineage.analysis_thread_id(
        document_id=document_id, authority=_authority(document_id=document_id)
    )
    assert lineage.is_authority_scoped_analysis_thread(scoped)
    assert not lineage.is_legacy_shared_analysis_thread(scoped)


def test_legacy_shared_threads_are_recognised() -> None:
    document_id = uuid4()
    shared = lineage.legacy_shared_analysis_thread_id(document_id)
    assert lineage.is_legacy_shared_analysis_thread(shared)
    assert not lineage.is_authority_scoped_analysis_thread(shared)


def test_unrelated_thread_shapes_are_neither() -> None:
    """A bare UUID thread is production's LEGACY shape and must match neither.

    Read-only production inspection found pending analysis_critique reviews on
    36-character UUID threads with no checkpoint id. They must not be treated
    as authority-scoped (which would let a claim rebind them) nor as the
    shared `document:{id}:analysis` form.
    """
    for candidate in (
        str(uuid4()),
        "",
        None,
        "thread_abc123",
        f"document:{uuid4()}:ingestion",
        f"document:{uuid4()}:g1:analysis",
        f"document:{uuid4()}:gX:fY:analysis",
        "document:not-a-uuid:g1:f1:analysis",
    ):
        assert not lineage.is_authority_scoped_analysis_thread(candidate)
        assert not lineage.is_legacy_shared_analysis_thread(candidate)
