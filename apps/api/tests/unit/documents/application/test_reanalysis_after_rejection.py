"""A human-rejected document can be re-analysed explicitly; a pending review or an analysed one cannot."""

import pytest

from src.documents.application.dtos import (
    DocumentLifecycleStatus,
    document_is_retryable,
    document_lifecycle_status,
)
from src.documents.domain.models import DocumentStatus


def test_rejected_document_is_retryable_but_pending_or_analyzed_are_not():
    rejected = document_lifecycle_status(
        DocumentStatus.NEEDS_CHANGES, has_pending_review=False, analysis_attempt_failed=False
    )
    assert rejected is DocumentLifecycleStatus.NEEDS_CHANGES
    assert document_is_retryable(rejected) is True

    pending = document_lifecycle_status(
        DocumentStatus.PARSED_PENDING_ANALYSIS, has_pending_review=True, analysis_attempt_failed=False
    )
    assert pending is DocumentLifecycleStatus.REVIEW_REQUIRED
    assert document_is_retryable(pending) is False
    assert document_is_retryable(DocumentLifecycleStatus.ANALYZED) is False
    assert document_is_retryable(DocumentLifecycleStatus.PROCESSING) is False


@pytest.mark.parametrize("status", [DocumentLifecycleStatus.ERROR, DocumentLifecycleStatus.FAILED_RETRYABLE])
def test_existing_retryable_states_stay_retryable(status):
    assert document_is_retryable(status) is True
