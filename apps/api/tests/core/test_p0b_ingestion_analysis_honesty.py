"""P0b ingestion honesty contract.

TS-UT-P0B-INGEST-HONESTY-001.

Production evidence (project 99a6001b, document ab813007) showed a contract that
reached ``upload_status = analyzed`` with 25 persisted clauses, zero RAG chunks,
and zero analyses / project_events / project_snapshots. Three fail-open layers
stacked to make total pipeline failure indistinguishable from success:

1. ``ingest_document_chunks`` swallowed every exception as a warning;
2. ``_run_document_analysis`` skipped the N1-N17 graph on ``no_rag_chunks``;
3. the document was marked ANALYZED regardless.

Each layer was individually defensible. Together they made ``analyzed``
unfalsifiable: it could not be distinguished from "we never analysed it".

These tests pin the corrected semantics. ANALYZED must mean the required
analysis actually completed -- or was legitimately not required for that
document type. It must never mean "structured extraction finished and the rest
silently did not happen".
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.documents.adapters.rag.rag_service import (
    RagProviderMisconfiguredError,
    RagProviderUnavailableError,
)
from src.documents.domain.models import Document, DocumentStatus, DocumentType
from src.documents.ports.rag_ingestion_service import (
    RagIngestionOutcome,
    RagIngestionResult,
)


def _document(document_type: DocumentType = DocumentType.CONTRACT) -> Document:
    return Document(
        id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        document_type=document_type,
        filename="contract.pdf",
        upload_status=DocumentStatus.PARSING,
    )


# ---------------------------------------------------------------------------
# Case A - free-text contract whose RAG ingestion failed.
# ---------------------------------------------------------------------------


def test_case_a_text_contract_without_rag_chunks_is_not_analyzed() -> None:
    """A contract whose graph never ran must not claim analysis success.

    This is the exact production shape: parsed_text present, clauses extracted,
    zero RAG chunks. The old code marked it ANALYZED.
    """
    from src.core.tasks.ingestion_tasks import decide_document_status

    status = decide_document_status(
        requires_text_analysis=True,
        rag_chunk_count=0,
        graph_analysis_id=None,
    )

    assert status is not DocumentStatus.ANALYZED
    assert status is DocumentStatus.PARSED_PENDING_ANALYSIS


def test_case_a_pending_state_remains_parsed_so_analysis_can_be_retried() -> None:
    """The degraded state must be retryable, not a dead end.

    ``_run_document_analysis`` refuses a document that is not ``is_parsed()``,
    so the chosen state has to keep that predicate true or a retry could never
    re-enter the pipeline.
    """
    document = _document()
    document.upload_status = DocumentStatus.PARSED_PENDING_ANALYSIS

    assert document.is_parsed() is True
    assert document.has_error() is False


def test_case_a_graph_failure_after_successful_rag_is_also_not_analyzed() -> None:
    """Chunks existed and the graph ran, but persistence failed -> not analyzed."""
    from src.core.tasks.ingestion_tasks import decide_document_status

    status = decide_document_status(
        requires_text_analysis=True,
        rag_chunk_count=12,
        graph_analysis_id=None,
    )

    assert status is DocumentStatus.PARSED_PENDING_ANALYSIS


# ---------------------------------------------------------------------------
# Case B - the happy path must still reach ANALYZED.
# ---------------------------------------------------------------------------


def test_case_b_text_contract_with_chunks_and_analysis_is_analyzed() -> None:
    from src.core.tasks.ingestion_tasks import decide_document_status

    status = decide_document_status(
        requires_text_analysis=True,
        rag_chunk_count=12,
        graph_analysis_id=str(uuid4()),
    )

    assert status is DocumentStatus.ANALYZED


# ---------------------------------------------------------------------------
# Case C - structured documents legitimately need no free-text graph.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("chunk_count", [0, 5])
def test_case_c_structured_document_without_graph_is_still_analyzed(
    chunk_count: int,
) -> None:
    """Schedule/budget documents carry no free text.

    Zero RAG chunks is the correct, complete outcome for them -- the fix must
    not fail every non-text document merely because it has no chunks.
    """
    from src.core.tasks.ingestion_tasks import decide_document_status

    status = decide_document_status(
        requires_text_analysis=False,
        rag_chunk_count=chunk_count,
        graph_analysis_id=None,
    )

    assert status is DocumentStatus.ANALYZED


# ---------------------------------------------------------------------------
# RAG error contract - four distinguishable outcomes, no silent success.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rag_misconfiguration_is_reported_not_swallowed() -> None:
    """A missing/invalid provider credential is a configuration failure.

    The old code logged a warning and returned None, which the caller could not
    distinguish from a successful ingestion.
    """
    from src.documents.adapters.rag.sqlalchemy_rag_ingestion_service import (
        SqlAlchemyRagIngestionService,
    )

    service = SqlAlchemyRagIngestionService(db_session=object())

    async def _raise(**_kwargs: object) -> int:
        raise RagProviderMisconfiguredError("OPENAI_API_KEY is not configured.")

    service._rag_service.ingest_document = _raise  # type: ignore[method-assign]

    result = await service.ingest_document_chunks(
        document=_document(),
        parsed_payload={"text": "A contract clause worth embedding."},
        tenant_id=uuid4(),
    )

    assert result.outcome is RagIngestionOutcome.MISCONFIGURED
    assert result.chunks == 0
    assert result.requires_attention is True


@pytest.mark.asyncio
async def test_rag_transient_provider_failure_is_distinguished_from_misconfiguration() -> None:
    from src.documents.adapters.rag.sqlalchemy_rag_ingestion_service import (
        SqlAlchemyRagIngestionService,
    )

    service = SqlAlchemyRagIngestionService(db_session=object())

    async def _raise(**_kwargs: object) -> int:
        raise RagProviderUnavailableError("upstream 503", status_code=503)

    service._rag_service.ingest_document = _raise  # type: ignore[method-assign]

    result = await service.ingest_document_chunks(
        document=_document(),
        parsed_payload={"text": "A contract clause worth embedding."},
        tenant_id=uuid4(),
    )

    assert result.outcome is RagIngestionOutcome.PROVIDER_UNAVAILABLE
    assert result.requires_attention is True


@pytest.mark.asyncio
async def test_rag_not_required_when_document_carries_no_embeddable_text() -> None:
    """Structured payloads legitimately need no RAG -- that is success, not failure."""
    from src.documents.adapters.rag.sqlalchemy_rag_ingestion_service import (
        SqlAlchemyRagIngestionService,
    )

    service = SqlAlchemyRagIngestionService(db_session=object())

    result = await service.ingest_document_chunks(
        document=_document(DocumentType.BUDGET),
        parsed_payload={},
        tenant_id=uuid4(),
    )

    assert result.outcome is RagIngestionOutcome.NOT_REQUIRED
    assert result.requires_attention is False


@pytest.mark.asyncio
async def test_rag_success_reports_chunk_count() -> None:
    from src.documents.adapters.rag.sqlalchemy_rag_ingestion_service import (
        SqlAlchemyRagIngestionService,
    )

    service = SqlAlchemyRagIngestionService(db_session=object())

    async def _ingest(**_kwargs: object) -> int:
        return 7

    service._rag_service.ingest_document = _ingest  # type: ignore[method-assign]

    result = await service.ingest_document_chunks(
        document=_document(),
        parsed_payload={"text": "A contract clause worth embedding."},
        tenant_id=uuid4(),
    )

    assert result.outcome is RagIngestionOutcome.INGESTED
    assert result.chunks == 7
    assert result.requires_attention is False


@pytest.mark.asyncio
async def test_rag_result_never_carries_provider_error_text_to_the_caller() -> None:
    """Provider messages can embed credentials or internal hosts.

    The typed result is the caller's contract; the raw message stays in the log.
    """
    from src.documents.adapters.rag.sqlalchemy_rag_ingestion_service import (
        SqlAlchemyRagIngestionService,
    )

    service = SqlAlchemyRagIngestionService(db_session=object())
    secret = "sk-live-DEADBEEF-should-never-surface"

    async def _raise(**_kwargs: object) -> int:
        raise RagProviderMisconfiguredError(f"bad key {secret} for https://internal.host")

    service._rag_service.ingest_document = _raise  # type: ignore[method-assign]

    result = await service.ingest_document_chunks(
        document=_document(),
        parsed_payload={"text": "A contract clause worth embedding."},
        tenant_id=uuid4(),
    )

    assert secret not in repr(result)
    assert "internal.host" not in repr(result)


def test_rag_ingestion_result_outcomes_are_exhaustive() -> None:
    """The four states the caller must be able to tell apart."""
    assert {outcome.value for outcome in RagIngestionOutcome} == {
        "ingested",
        "not_required",
        "provider_unavailable",
        "misconfigured",
    }


def test_only_ingested_and_not_required_permit_analyzed() -> None:
    """The result alone decides whether ANALYZED is defensible."""
    permitting = {
        outcome
        for outcome in RagIngestionOutcome
        if not RagIngestionResult(outcome=outcome).requires_attention
    }

    assert permitting == {RagIngestionOutcome.INGESTED, RagIngestionOutcome.NOT_REQUIRED}


# ---------------------------------------------------------------------------
# Retry matrix. "Re-enterable state" is not "a retry happened" -- the Celery
# task declares autoretry_for=(Exception,) with max_retries=3, so a normal
# return is a COMPLETED task no matter how honest its payload.
# ---------------------------------------------------------------------------


def test_misconfigured_does_not_schedule_a_pointless_retry() -> None:
    """An operator must act; three backoff retries would change nothing."""
    from src.core.tasks.ingestion_tasks import should_retry_analysis

    assert (
        should_retry_analysis(
            status=DocumentStatus.PARSED_PENDING_ANALYSIS,
            rag_outcome=RagIngestionOutcome.MISCONFIGURED.value,
        )
        is False
    )


@pytest.mark.parametrize(
    "rag_outcome",
    [
        RagIngestionOutcome.PROVIDER_UNAVAILABLE.value,
        None,  # unknown: treat as plausibly transient
    ],
)
def test_transient_failures_do_schedule_a_bounded_retry(rag_outcome: str | None) -> None:
    from src.core.tasks.ingestion_tasks import should_retry_analysis

    assert (
        should_retry_analysis(
            status=DocumentStatus.PARSED_PENDING_ANALYSIS, rag_outcome=rag_outcome
        )
        is True
    )


def test_graph_failure_after_successful_rag_is_retried() -> None:
    """Chunks existed, so the provider is fine; the graph run itself is retryable."""
    from src.core.tasks.ingestion_tasks import should_retry_analysis

    assert (
        should_retry_analysis(
            status=DocumentStatus.PARSED_PENDING_ANALYSIS,
            rag_outcome=RagIngestionOutcome.INGESTED.value,
        )
        is True
    )


def test_completed_analysis_never_retries() -> None:
    from src.core.tasks.ingestion_tasks import should_retry_analysis

    for outcome in RagIngestionOutcome:
        assert (
            should_retry_analysis(status=DocumentStatus.ANALYZED, rag_outcome=outcome.value)
            is False
        )


def test_analysis_task_declares_the_bounded_retry_this_relies_on() -> None:
    """The raise is only useful because the task actually auto-retries.

    Pinning it here means a future change to the task options cannot silently
    turn every transient failure into a one-shot give-up.
    """
    from src.core.tasks.ingestion_tasks import ANALYSIS_TASK_RETRY_OPTIONS

    # Single-sourced with the decorator, so this cannot pass while the real task
    # has quietly stopped retrying. (Celery is stubbed suite-wide, so the task
    # registry itself is not observable from tests.)
    assert Exception in ANALYSIS_TASK_RETRY_OPTIONS["autoretry_for"]
    assert ANALYSIS_TASK_RETRY_OPTIONS["retry_kwargs"]["max_retries"] == 3
    assert ANALYSIS_TASK_RETRY_OPTIONS["retry_backoff"] is True


def test_retryable_error_is_an_exception_so_celery_autoretry_catches_it() -> None:
    from src.core.tasks.ingestion_tasks import AnalysisIncompleteRetryableError

    assert issubclass(AnalysisIncompleteRetryableError, Exception)


# ---------------------------------------------------------------------------
# Document-type contract. bool(parsed_text) alone is NOT the predicate.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "document_type",
    [DocumentType.CONTRACT, DocumentType.TECHNICAL_SPEC, DocumentType.SPECIFICATION],
)
def test_free_text_documents_require_the_graph(document_type: DocumentType) -> None:
    from src.core.tasks.ingestion_tasks import requires_text_analysis

    assert requires_text_analysis(document_type, "real contract text") is True


@pytest.mark.parametrize(
    "document_type",
    [DocumentType.SCHEDULE, DocumentType.BUDGET, DocumentType.DRAWING, DocumentType.OTHER],
)
def test_structured_documents_are_not_held_pending_by_incidental_parser_text(
    document_type: DocumentType,
) -> None:
    """The regression this predicate exists to prevent.

    ``composite_file_parser`` emits ``text_blocks`` for ANY PDF or DOCX, so a
    schedule or budget uploaded as a PDF carries incidental parsed text. Keying
    on text alone would strand it pending forever waiting for a graph run it
    never needed -- swapping the old false-success bug for a false-incomplete
    one.
    """
    from src.core.tasks.ingestion_tasks import requires_text_analysis

    assert requires_text_analysis(document_type, "incidental text from the PDF parser") is False


def test_free_text_document_without_any_text_cannot_be_owed_a_graph_run() -> None:
    from src.core.tasks.ingestion_tasks import requires_text_analysis

    assert requires_text_analysis(DocumentType.CONTRACT, None) is False
    assert requires_text_analysis(DocumentType.CONTRACT, "") is False


def test_structured_document_reaches_analyzed_without_the_graph() -> None:
    """End of the contract: schedule/budget stay terminally ANALYZED."""
    from src.core.tasks.ingestion_tasks import decide_document_status, requires_text_analysis

    status = decide_document_status(
        requires_text_analysis=requires_text_analysis(DocumentType.BUDGET, "incidental"),
        rag_chunk_count=0,
        graph_analysis_id=None,
    )

    assert status is DocumentStatus.ANALYZED
