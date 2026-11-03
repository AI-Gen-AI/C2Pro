"""The fourth PQ-HITL-09 family (technical specification) through the real worker (ACC-01 S2/S3).

REAL PostgreSQL, a REAL ``.docx`` specification, the REAL ingestion worker and ``/coherence/evaluate``.
It pins what is true TODAY, honestly: the specification is accepted, stored under a pinned revision and
processed without error, but it yields no coherence evidence (no clauses), so the TECHNICAL dimension
stays withheld and the score stays NULL with its reason. When specification clauses are extracted this
test is the one to tighten (TECHNICAL assessed); it must never be satisfied by a fabricated coverage.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.documents.domain.models import DocumentType
from tests.integration.document_flow.test_contract_schedule_completion_flow import (
    COMPLETION_CLAUSE,
    LATE_SCHEDULE,
    PRICE_CLAUSE,
    _docx,
    _evaluate,
    _scenario,
    _upload_and_ingest,
    worker,  # noqa: F401  (pytest fixture)
)

pytestmark = pytest.mark.asyncio

SPEC = [
    "Section 4.1.2 Concrete compressive strength shall exceed 35 MPa at 28 days.",
    "Section 4.2 Reinforcement steel shall be B500S.",
]


async def test_a_technical_specification_is_ingested_but_does_not_fabricate_technical_coverage(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id, *_ = await _scenario(
        db, worker, test_user, contract=[PRICE_CLAUSE, COMPLETION_CLAUSE], schedule=LATE_SCHEDULE
    )
    spec, revision = await _upload_and_ingest(
        db, worker, test_user, project_id, filename="specification.docx",
        content=_docx(SPEC), document_type=DocumentType.TECHNICAL_SPEC,
    )

    state = (
        await db.execute(
            text("SELECT upload_status::text AS status, parsing_error AS error, document_type::text AS doc_type "
                 "FROM documents WHERE id = :d"),
            {"d": spec.id},
        )
    ).one()
    assert state.doc_type == "technical_spec" and state.error is None
    assert str(revision.revision_id), "stored under a pinned, content-addressed revision"

    result = await _evaluate(db, test_user, project_id)

    assert result.overall_score is None, "no score without valid coverage"
    assert "TECHNICAL" in (result.score_missing_dimensions or []), "TECHNICAL stays unmeasured, not green or zero"
    assert "AUDIT_INCOMPLETE" in {a.rule_id for a in result.alerts}
