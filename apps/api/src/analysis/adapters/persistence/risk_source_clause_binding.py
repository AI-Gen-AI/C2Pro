"""Resolve TRUSTED artifact risks to physical persisted clause IDs (read-only).

ProjectGraph N4 signals otherwise carry the artifact revision surrogate as
``clause_id``. A physical ``clauses.id`` is returned here only when the risk's
quote is VERIFIED (found verbatim; not a statement that the risk is valid), its
``clause_ref`` is an explicit numeric code and the shared exact resolver finds
exactly one persisted clause in this tenant/project/document/revision. Anything
else is simply absent from the mapping, so the caller keeps the surrogate.
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from contextlib import AbstractAsyncContextManager, nullcontext
from typing import Any
from uuid import UUID

from src.analysis.adapters.graph.review_source_references import (
    grounded_review_source_references,
    review_risk_clause_codes,
    risk_source_key,
)
from src.analysis.domain.contracts import DocumentArtifact
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)

logger = logging.getLogger(__name__)

VERIFIED_QUOTE_STATUS = "VERIFIED"


def _uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _savepoint(session: Any) -> AbstractAsyncContextManager[Any]:
    begin_nested = getattr(session, "begin_nested", None)
    return begin_nested() if callable(begin_nested) else nullcontext()


async def load_trusted_risk_source_clause_ids(
    session: Any,
    *,
    tenant_id: UUID | str,
    project_id: UUID | str,
    artifacts: Sequence[DocumentArtifact],
    repository: Any | None = None,
) -> dict[str, str]:
    """Return ``{doc|rev|numeric_ref: physical clause UUID}`` for resolvable risks."""
    tenant, project = _uuid(tenant_id), _uuid(project_id)
    if tenant is None or project is None:
        return {}
    repo = repository or SqlAlchemyDocumentRepository(session)
    mapping: dict[str, str] = {}
    for artifact in artifacts:
        document, revision = _uuid(artifact.document_id), _uuid(artifact.document_revision_id)
        if document is None or revision is None:
            continue
        codes = review_risk_clause_codes([
            risk.model_dump(mode="json")
            for risk in artifact.extracted_risks
            if risk.source_quote_status == VERIFIED_QUOTE_STATUS
        ])
        if not codes:
            continue
        try:
            # Savepoint: a failed read must not poison the run's transaction.
            async with _savepoint(session):
                clauses = await repo.list_clauses_bound_to_revision(tenant, document, revision)
        except Exception:  # noqa: BLE001 - fail closed to the revision surrogate
            logger.warning(
                "risk_source_clause_binding.lookup_failed",
                extra={"document_id": str(document), "revision_id": str(revision)},
            )
            continue
        for ref in grounded_review_source_references(
            tenant_id=tenant, project_id=project, document_id=document,
            revision_id=revision, clause_codes=codes, persisted_clauses=clauses,
        ):
            key = risk_source_key(ref["document_id"], ref["revision_id"], ref["clause_code"])
            if key is not None:
                mapping[key] = ref["clause_id"]
    return mapping


__all__ = ["load_trusted_risk_source_clause_ids"]
