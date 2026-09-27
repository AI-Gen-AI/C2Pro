"""#711 recovery classification contracts.

These tests define the bounded recovery decision independently from database
scanning so tenant/RLS plumbing cannot blur the product semantics.
"""
from __future__ import annotations

from src.core.tasks.document_recovery import (
    MAX_RECOVERY_ATTEMPTS,
    _SCAN_SQL,
    RecoveryAction,
    classify_stale_document,
    recovery_attempts_for,
)
from src.documents.domain.models import DocumentStatus
from src.documents.ports.rag_ingestion_service import RagIngestionOutcome


def test_stale_parsing_requeues_ingestion() -> None:
    assert (
        classify_stale_document(
            status=DocumentStatus.PARSING,
            hitl_pending=False,
            attempts=0,
            rag_outcome=None,
        )
        is RecoveryAction.REQUEUE_INGESTION
    )


def test_stale_analysis_pending_requeues_analysis() -> None:
    assert (
        classify_stale_document(
            status=DocumentStatus.PARSED_PENDING_ANALYSIS,
            hitl_pending=False,
            attempts=0,
            rag_outcome=RagIngestionOutcome.INGESTED.value,
        )
        is RecoveryAction.REQUEUE_ANALYSIS
    )


def test_hitl_pending_is_never_recovered_as_abandoned_work() -> None:
    assert (
        classify_stale_document(
            status=DocumentStatus.PARSED_PENDING_ANALYSIS,
            hitl_pending=True,
            attempts=0,
            rag_outcome=RagIngestionOutcome.INGESTED.value,
        )
        is RecoveryAction.SKIP
    )


def test_exhausted_recovery_budget_becomes_retryable_failure() -> None:
    assert (
        classify_stale_document(
            status=DocumentStatus.PARSING,
            hitl_pending=False,
            attempts=MAX_RECOVERY_ATTEMPTS,
            rag_outcome=None,
        )
        is RecoveryAction.FAIL_RETRYABLE
    )


def test_provider_misconfiguration_does_not_burn_transient_retries() -> None:
    assert (
        classify_stale_document(
            status=DocumentStatus.PARSED_PENDING_ANALYSIS,
            hitl_pending=False,
            attempts=0,
            rag_outcome=RagIngestionOutcome.MISCONFIGURED.value,
        )
        is RecoveryAction.FAIL_RETRYABLE
    )


def test_recovery_attempt_budget_is_scoped_to_stage_and_document_generation() -> None:
    metadata = {
        "processing_recovery": {
            "stage": DocumentStatus.PARSING.value,
            "generation": "v2:revision-b",
            "attempts": 2,
        }
    }

    assert (
        recovery_attempts_for(
            metadata,
            stage=DocumentStatus.PARSING,
            generation="v2:revision-b",
        )
        == 2
    )
    assert (
        recovery_attempts_for(
            metadata,
            stage=DocumentStatus.PARSED_PENDING_ANALYSIS,
            generation="v2:revision-b",
        )
        == 0
    )
    assert (
        recovery_attempts_for(
            metadata,
            stage=DocumentStatus.PARSING,
            generation="v3:revision-c",
        )
        == 0
    )



def test_cross_tenant_discovery_uses_narrow_security_definer_surface() -> None:
    sql = str(_SCAN_SQL)
    assert "system_recovery.list_stale_document_candidates" in sql
    assert "FROM documents" not in sql
    assert "FROM public.documents" not in sql
