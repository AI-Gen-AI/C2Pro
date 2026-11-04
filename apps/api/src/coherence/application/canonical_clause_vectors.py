"""Opt-in indexing of canonical, revision-bound EPC clause evidence.

This is an *index*, not a source of truth or an assessment. Only an explicitly
invoked index operation may call the embedding provider. N8 remains able to run
without vectors and may not manufacture missing documents or trusted status.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.documents.adapters.rag.rag_service import (
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
    _embed_texts,
)
from src.temporal.adapters.persistence.current_revision_sql import current_revision_lateral

EmbeddingProvider = Callable[[list[str]], Awaitable[list[list[float]]]]

# SOURCE authority: contracts require canonical; technical specifications must
# be explicitly trusted (a merely proposed requirement is not compliance).
_CURRENT_CLAUSE_SOURCES = text(f"""
SELECT c.id::text AS clause_id, c.full_text, c.revision_id::text AS revision_id,
       (c.extracted_entities ->> 'source_page') AS source_page,
       c.text_start_offset, c.text_end_offset,
       d.id::text AS document_id, d.document_type::text AS document_type,
       ce.metadata AS existing_metadata
FROM public.clauses AS c
JOIN public.documents AS d ON d.id = c.document_id
  AND d.project_id = c.project_id AND d.tenant_id = c.tenant_id
CROSS JOIN LATERAL {current_revision_lateral("d.id", "d.tenant_id")} AS cur
LEFT JOIN public.clause_embeddings AS ce
  ON ce.clause_id = c.id::text
 AND ce.project_id = c.project_id AND ce.tenant_id = c.tenant_id
WHERE c.tenant_id = CAST(:tenant_id AS uuid)
  AND c.project_id = CAST(:project_id AS uuid)
  AND c.id::text = ANY(CAST(:clause_ids AS text[]))
  AND c.revision_id IS NOT NULL
  AND c.revision_id = cur.revision_id
  AND ((
      d.document_type::text = 'contract' AND cur.canonical
  ) OR (
      d.document_type::text IN ('technical_spec', 'specification') AND cur.trusted
  ))
  AND length(btrim(c.full_text)) > 0
ORDER BY c.id
LIMIT :limit
""")

# Recheck source authority at INSERT time: if trust/revision changes during
# embedding generation, no stale vector may be created or promoted.
_WRITE_CURRENT_CLAUSE_VECTOR = text(f"""
INSERT INTO public.clause_embeddings
 (tenant_id, clause_id, project_id, document_id, document_type, text,
  embedding, category, metadata)
SELECT c.tenant_id, c.id::text, c.project_id, d.id, d.document_type::text,
       c.full_text, CAST(:embedding AS vector), :category,
       CAST(:metadata AS jsonb)
FROM public.clauses AS c
JOIN public.documents AS d ON d.id = c.document_id
  AND d.tenant_id = c.tenant_id AND d.project_id = c.project_id
CROSS JOIN LATERAL {current_revision_lateral("d.id", "d.tenant_id")} AS cur
WHERE c.tenant_id = CAST(:tenant_id AS uuid)
  AND c.project_id = CAST(:project_id AS uuid)
  AND c.id::text = :clause_id
  AND d.id = CAST(:document_id AS uuid)
  AND c.revision_id = CAST(:revision_id AS uuid)
  AND c.revision_id = cur.revision_id
  AND c.full_text = :source_text
  AND ((
       d.document_type::text = 'contract' AND cur.canonical
  ) OR (
       d.document_type::text IN ('technical_spec', 'specification') AND cur.trusted
  ))
ON CONFLICT (clause_id, project_id) DO UPDATE SET
   embedding = EXCLUDED.embedding,
   text = EXCLUDED.text,
   document_type = EXCLUDED.document_type,
   category = EXCLUDED.category,
   metadata = EXCLUDED.metadata,
   created_at = now()
WHERE clause_embeddings.tenant_id = EXCLUDED.tenant_id
  AND clause_embeddings.document_id = EXCLUDED.document_id
RETURNING id
""")


def _source_metadata(row: dict[str, Any]) -> dict[str, Any]:
    txt = str(row["full_text"])
    metadata: dict[str, Any] = {
        "revision_id": str(row["revision_id"]),
        "document_id": str(row["document_id"]),
        "embedding_model": EMBEDDING_MODEL,
        "text_sha256": hashlib.sha256(txt.encode("utf-8")).hexdigest(),
    }
    if row.get("source_page") is not None:
        metadata["source_page"] = row["source_page"]
    for attr in ("text_start_offset", "text_end_offset"):
        if row.get(attr) is not None:
            metadata[attr] = row[attr]
    return metadata


def _validated_vector(embedding: list[float]) -> str:
    if len(embedding) != EMBEDDING_DIMENSION:
        raise ValueError("CANONICAL_EMBEDDING_WRONG_DIMENSIONS")
    if not all(isinstance(value, int | float) and math.isfinite(value) for value in embedding):
        raise ValueError("CANONICAL_EMBEDDING_NON_FINITE")
    if not any(value != 0 for value in embedding):
        raise ValueError("CANONICAL_EMBEDDING_ZERO_VECTOR")
    return "[" + ",".join(str(float(value)) for value in embedding) + "]"


async def index_current_clause_vectors(
    *,
    db: AsyncSession,
    tenant_id: UUID,
    project_id: UUID,
    clause_ids: list[str],
    embed: EmbeddingProvider = _embed_texts,
    max_units: int = 50,
) -> dict[str, Any]:
    """Index eligible current clauses, preserving revision and tenant authority.

    Caller owns the transaction and must commit it; no hidden commit.
    Set the tenant GUC only after verifying the project belongs to that tenant.
    Only clauses explicitly selected by the canonical N8 input are indexed.
    """
    if max_units < 1 or max_units > 200:
        raise ValueError("CANONICAL_EMBEDDING_INVALID_BATCH_LIMIT")
    if not clause_ids:
        return {"state": "NO_SOURCE_CLAUSES", "indexed": 0, "unchanged": 0}

    belongs = await db.scalar(
        text("""
            SELECT EXISTS(
                SELECT 1 FROM public.projects
                WHERE id = CAST(:project_id AS uuid)
                  AND tenant_id = CAST(:tenant_id AS uuid)
            )
        """),
        {"tenant_id": str(tenant_id), "project_id": str(project_id)},
    )
    if not belongs:
        raise PermissionError("CANONICAL_EMBEDDING_FOREIGN_PROJECT")
    await db.execute(
        text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )

    result = await db.execute(
        _CURRENT_CLAUSE_SOURCES,
        {
            "tenant_id": str(tenant_id),
            "project_id": str(project_id),
            "clause_ids": list(dict.fromkeys(clause_ids)),
            "limit": max_units + 1,
        },
    )
    sources = [dict(row) for row in result.mappings().all()]
    overflow = len(sources) > max_units
    sources = sources[:max_units]

    pending: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for row in sources:
        metadata = _source_metadata(row)
        existing = row.get("existing_metadata") or {}
        if not isinstance(existing, dict) or any(
            existing.get(key) != val for key, val in metadata.items()
        ):
            pending.append((row, metadata))

    if not pending:
        return {
            "state": "PARTIAL" if overflow else "CURRENT",
            "indexed": 0, "unchanged": len(sources),
            "additional_units_unassessed": overflow,
        }

    vectors = await embed([row["full_text"] for row, _ in pending])
    if len(vectors) != len(pending):
        raise ValueError("CANONICAL_EMBEDDING_PROVIDER_COUNT_MISMATCH")
    encodings = [_validated_vector(vector) for vector in vectors]

    written = 0
    for (row, metadata), embedding in zip(pending, encodings, strict=True):
        response = await db.execute(
            _WRITE_CURRENT_CLAUSE_VECTOR,
            {
                "tenant_id": str(tenant_id),
                "project_id": str(project_id),
                "clause_id": row["clause_id"],
                "document_id": row["document_id"],
                "revision_id": row["revision_id"],
                "source_text": row["full_text"],
                "category": (
                    "TECHNICAL"
                    if row["document_type"] in {"technical_spec", "specification"}
                    else "SCOPE"
                ),
                "metadata": json.dumps(metadata, sort_keys=True),
                "embedding": embedding,
            },
        )
        if response.scalar_one_or_none() is None:
            # The document may have been promoted, retired or moved while
            # embeddings were generated. Do not silently call this complete.
            raise RuntimeError("CANONICAL_EMBEDDING_SOURCE_CHANGED")
        written += 1
    return {
        "state": "PARTIAL" if overflow else "CURRENT",
        "indexed": written,
        "unchanged": len(sources) - len(pending),
        "additional_units_unassessed": overflow,
        "embedding_model": EMBEDDING_MODEL,
    }


__all__ = ["index_current_clause_vectors"]
