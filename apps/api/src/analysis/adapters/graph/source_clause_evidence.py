"""Revision-bound source-fact quotes for unscored EPC comparisons.

These are literal spans of ingested source text, never generated findings or
human-verified legal interpretations. The reader requires a current revision,
and ProjectGraph additionally requires TRUSTED analytic artifacts for their
documents before these quotes can affect a provisional comparison.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.temporal.adapters.persistence.current_revision_sql import current_revision_lateral

# Limited, conservative evidence discovery only. Ambiguous or unsupported
# wording is not assessed; no inferred price/deadline is produced.
_FIELDS: dict[str, tuple[re.Pattern[str], ...]] = {
    "contract": tuple(re.compile(p, re.IGNORECASE) for p in (
        r"\b(?:the\s+)?total\s+contract\s+price\s+is\s+(?:EUR|USD|GBP|€)\s*\d[\d,]*(?:\.\d{1,2})?",
        r"\b(?:el\s+)?precio\s+del\s+contrato\s+(?:asciende\s+a|es\s+de)\s+\d[\d.,]*\s*(?:euros?|EUR|USD|GBP|€)",
        r"\bcontractual\s+completion\s+deadline\s+is\s+20\d{2}-\d{2}-\d{2}",
        r"\bfecha\s+de\s+finalizaci[oó]n[^.]{0,100}?(?:20\d{2}-\d{2}-\d{2}|\d{1,2}\s+de\s+\w+\s+de\s+20\d{2})",
    )),
    "technical_spec": tuple(re.compile(p, re.IGNORECASE) for p in (
        r"\bfactory\s+acceptance\s+testing\s+shall\s+be\s+completed\s+no\s+later\s+than\s+20\d{2}-\d{2}-\d{2}",
        r"\bpruebas\s+de\s+aceptaci[oó]n\s+en\s+f[aá]brica[^.]{0,110}?(?:20\d{2}-\d{2}-\d{2}|\d{1,2}\s+de\s+\w+\s+de\s+20\d{2})",
    )),
}


def extract_literal_source_quotes(
    *, document_id: str, revision_id: str, chunk_id: str,
    doc_type: str, content: str,
) -> list[dict[str, Any]]:
    """Return spans whose wording exists verbatim in the revision-stamped chunk."""
    if doc_type not in _FIELDS or not content or len(content) > 500_000:
        return []
    results: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for pattern in _FIELDS[doc_type]:
        for match in pattern.finditer(content):
            if match.span() in seen:
                continue
            seen.add(match.span())
            quote = content[match.start():match.end()]
            results.append({
                "document_id": str(document_id),
                "revision_id": str(revision_id),
                "doc_type": doc_type,
                "source_locator": f"chunk:{chunk_id}:{match.start()}-{match.end()}",
                "source_quote": quote,
                "source_quote_sha256": hashlib.sha256(quote.encode("utf-8")).hexdigest(),
            })
    return results


_CHUNKS = text(f"""
    SELECT c.document_id, c.id AS chunk_id, c.content,
           c.metadata->>'revision_id' AS revision_id,
           d.document_type::text AS doc_type
    FROM public.document_chunks AS c
    JOIN public.documents AS d ON d.id = c.document_id
      AND d.project_id = c.project_id AND d.tenant_id = c.tenant_id
    CROSS JOIN LATERAL {current_revision_lateral("c.document_id", "c.tenant_id")} AS cur
    WHERE c.project_id = CAST(:project_id AS uuid)
      AND c.tenant_id = CAST(:tenant_id AS uuid)
      AND d.document_type::text IN ('contract', 'technical_spec')
      AND cur.resolved AND cur.revision_id::text = c.metadata->>'revision_id'
      AND c.content IS NOT NULL
    ORDER BY c.document_id, c.id
    LIMIT 501
""")


async def load_revision_bound_source_quotes(
    *, session: AsyncSession, tenant_id: UUID, project_id: UUID,
) -> list[dict[str, Any]]:
    """Read exact clauses from parsed chunks with current tenant/revision lineage."""
    rows = (await session.execute(
        _CHUNKS, {"tenant_id": str(tenant_id), "project_id": str(project_id)}
    )).mappings().all()
    if len(rows) > 500:
        # No silent partial coverage of a larger document collection.
        raise ValueError("SOURCE_FACT_CHUNK_LIMIT_EXCEEDED")
    return [
        item
        for row in rows
        for item in extract_literal_source_quotes(
            document_id=str(row["document_id"]),
            revision_id=str(row["revision_id"]),
            chunk_id=str(row["chunk_id"]),
            doc_type=str(row["doc_type"]),
            content=str(row["content"]),
        )
    ]


__all__ = ["extract_literal_source_quotes", "load_revision_bound_source_quotes"]
