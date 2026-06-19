"""Freeze-lock tests for DocumentRevision domain contract (ADR-015 / TASK-V3-015-01)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.temporal.domain.document_revision import DocumentRevision


def test_revision_is_frozen():
    rev = DocumentRevision(
        revision_id=uuid4(),
        document_id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        rev_no=1,
        blob_hash="abc123",
        blob_key="revisions/abc123.pdf",
        valid_from=datetime.now(UTC).replace(tzinfo=None),
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    with pytest.raises(ValidationError):
        rev.rev_no = 2


def test_revision_forbids_extra_keys():
    with pytest.raises(ValidationError):
        DocumentRevision(
            revision_id=uuid4(),
            document_id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            rev_no=1,
            blob_hash="abc",
            blob_key="k",
            valid_from=datetime.now(UTC).replace(tzinfo=None),
            created_at=datetime.now(UTC).replace(tzinfo=None),
            bogus=1,
        )


def test_first_revision_parent_is_none():
    rev = DocumentRevision(
        revision_id=uuid4(),
        document_id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        rev_no=1,
        blob_hash="abc",
        blob_key="k",
        valid_from=datetime.now(UTC).replace(tzinfo=None),
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    assert rev.parent_revision_id is None


def test_later_revision_has_parent():
    parent_id = uuid4()
    rev = DocumentRevision(
        revision_id=uuid4(),
        document_id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        rev_no=2,
        parent_revision_id=parent_id,
        blob_hash="def",
        blob_key="k2",
        valid_from=datetime.now(UTC).replace(tzinfo=None),
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    assert rev.parent_revision_id == parent_id


def test_valid_to_is_optional():
    rev = DocumentRevision(
        revision_id=uuid4(),
        document_id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        rev_no=1,
        blob_hash="abc",
        blob_key="k",
        valid_from=datetime.now(UTC).replace(tzinfo=None),
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    assert rev.valid_to is None
