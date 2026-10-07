"""Decision Intelligence retrieval port adapter.

Performs semantic retrieval against the shared ``document_chunks``
pgvector table using OpenAI embeddings, restricted to the caller's tenant
AND project, ordered by cosine distance, returning the top-k results as
``[{"text", "score"}]``.

SECURITY (P0): the application connects with a role that bypasses RLS, so
the tenant and project are bound in the SQL itself. Without both, no query
runs (fail closed): never a cross-tenant or cross-project read.

When embeddings or the database are unavailable, the adapter falls
back to a deterministic evidence stub so the decision flow can still
make progress.

Refers to Suite ID: TS-I13-E2E-REAL-001.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.temporal.adapters.persistence.current_revision_sql import (
    chunk_in_current_scope,
    current_chunk_join,
)

logger = structlog.get_logger()

_TOP_K = 5

SessionProvider = Callable[[], AbstractAsyncContextManager[AsyncSession]]
EmbedFn = Callable[[list[str]], Awaitable[list[list[float]]]]


class RetrievalPortAdapter:
    """Real RetrievalPort implementation backed by pgvector."""

    def __init__(
        self,
        *,
        session_provider: SessionProvider,
        embed_fn: EmbedFn,
        top_k: int = _TOP_K,
    ) -> None:
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        self._session_provider = session_provider
        self._embed_fn = embed_fn
        self._top_k = top_k

    async def retrieve(
        self, query: str, *, tenant_id: UUID | None, project_id: UUID | None
    ) -> list[dict[str, Any]]:
        if not query:
            return self._fallback_evidence()
        if tenant_id is None or project_id is None:
            logger.warning("di_retrieval_unscoped_refused")
            return self._fallback_evidence()

        try:
            embeddings = await self._embed_fn([query])
        except Exception as exc:
            logger.warning("di_retrieval_embed_failed", error=str(exc))
            return self._fallback_evidence()

        if not embeddings or not embeddings[0]:
            return self._fallback_evidence()

        vector_literal = _format_vector(embeddings[0])
        try:
            async with self._session_provider() as session:
                rows = await self._fetch_chunks(session, vector_literal, tenant_id, project_id)
        except Exception as exc:
            logger.warning("di_retrieval_db_failed", error=str(exc))
            return self._fallback_evidence()

        if not rows:
            return self._fallback_evidence()

        results: list[dict[str, Any]] = []
        for row in rows:
            content = str(row[0] or "").strip()
            if not content:
                continue
            distance = float(row[1]) if row[1] is not None else 1.0
            score = max(0.0, 1.0 - distance)
            results.append({"text": content, "score": round(score, 6)})
        return results or self._fallback_evidence()

    async def _fetch_chunks(
        self,
        session: AsyncSession,
        vector_literal: str,
        tenant_id: UUID,
        project_id: UUID,
    ) -> list[Any]:
        # Lane C / C3a: only each document's trusted-current revision is evidence.
        # P0: tenant AND project bound here -- RLS is bypassed by the application role.
        stmt = text(
            f"""
            SELECT dc.content, dc.embedding <-> CAST(:embedding AS vector) AS distance
            FROM document_chunks dc
            {current_chunk_join("dc")}
            WHERE dc.tenant_id = CAST(:tenant_id AS uuid)
              AND dc.project_id = CAST(:project_id AS uuid)
              AND {chunk_in_current_scope("dc", "cur")}
            ORDER BY distance ASC
            LIMIT :top_k
            """
        )
        result = await session.execute(
            stmt,
            {
                "embedding": vector_literal,
                "top_k": self._top_k,
                "tenant_id": str(tenant_id),
                "project_id": str(project_id),
            },
        )
        return list(result.fetchall())

    @staticmethod
    def _fallback_evidence() -> list[dict[str, Any]]:
        return [
            {
                "text": "No semantic evidence available for query; using baseline evidence.",
                "score": 0.5,
            }
        ]


def _format_vector(embedding: list[float]) -> str:
    return "[" + ",".join(f"{value:.6f}" for value in embedding) + "]"
