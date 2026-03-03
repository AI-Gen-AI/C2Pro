"""
I12 - Trace Context Invariants (Domain, RED)
Test Suite ID: TS-I12-OBS-DOM-002
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.modules.observability.domain.entities import TraceContext


def test_i12_trace_context_requires_tenant_and_project_metadata_red() -> None:
    """
    TS-I12-OBS-DOM-002:
    trace metadata must include tenant_id and project_id for auditability.
    """
    with pytest.raises(ValidationError, match="tenant_id"):
        TraceContext(
            name="decision_run",
            run_type="chain",
            metadata={"project_id": "project-a"},
        )

    with pytest.raises(ValidationError, match="project_id"):
        TraceContext(
            name="decision_run",
            run_type="chain",
            metadata={"tenant_id": "tenant-a"},
        )


def test_i12_trace_context_parent_id_cannot_equal_run_id_red() -> None:
    """
    TS-I12-OBS-DOM-002:
    parent-child lineage must not allow self-referential parent_id.
    """
    run_id = uuid4()

    with pytest.raises(ValidationError, match="parent_id"):
        TraceContext(
            run_id=run_id,
            parent_id=run_id,
            name="self_parent",
            run_type="tool",
            metadata={"tenant_id": "tenant-a", "project_id": "project-a"},
        )


def test_i12_trace_context_metadata_values_must_be_string_serializable_red() -> None:
    """
    TS-I12-OBS-DOM-002:
    metadata values must be string-serializable scalars for stable trace export.
    """
    with pytest.raises(ValidationError, match="metadata"):
        TraceContext(
            name="bad_metadata",
            run_type="agent",
            metadata={
                "tenant_id": "tenant-a",
                "project_id": "project-a",
                "complex": {"nested": "not-allowed"},
            },
        )
