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
    risk_quote_source_key,
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
    """Return ``{doc|rev|code|sha256(quote): physical clause UUID}`` per resolvable risk."""
    tenant, project = _uuid(tenant_id), _uuid(project_id)
    if tenant is None or project is None:
        return {}
    repo = repository or SqlAlchemyDocumentRepository(session)
    mapping: dict[str, str] = {}
    for artifact in artifacts:
        document, revision = _uuid(artifact.document_id), _uuid(artifact.document_revision_id)
        if document is None or revision is None:
            continue
        candidates = [
            (risk, code)
            for risk in artifact.extracted_risks
            if risk.source_quote_status == VERIFIED_QUOTE_STATUS
            and isinstance(risk.source_quote, str)
            and risk.source_quote.strip()
            and (codes := review_risk_clause_codes([{"clause_ref": risk.clause_ref}]))
            for code in codes
        ]
        if not candidates:
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
        by_id = {getattr(c, "id", None): c for c in clauses}
        resolved: dict[str, Any] = {}
        for risk, code in candidates:
            if code not in resolved:
                refs = grounded_review_source_references(
                    tenant_id=tenant, project_id=project, document_id=document,
                    revision_id=revision, clause_codes={code}, persisted_clauses=clauses,
                )
                resolved[code] = refs[0] if len(refs) == 1 else None
            ref = resolved[code]
            clause = by_id.get(_uuid(ref["clause_id"])) if ref else None
            full_text = getattr(clause, "full_text", None)
            # The quote must sit verbatim inside THIS physical clause (no
            # normalisation); a missing legacy full_text fails closed.
            if not isinstance(full_text, str) or risk.source_quote not in full_text:
                continue
            key = risk_quote_source_key(document, revision, code, risk.source_quote)
            if key is not None:
                mapping[key] = str(clause.id)
    return mapping


__all__ = ["load_trusted_risk_source_clause_ids"]
