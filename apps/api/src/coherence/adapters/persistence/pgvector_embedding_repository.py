"""
Pgvector Embedding Repository Adapter for Coherence Engine v0.3 — Phase 6

Implements the IEmbeddingRepository port using PostgreSQL with pgvector extension
for efficient cosine similarity search on clause embeddings.

This adapter provides zero-LLM-cost similarity detection for cross-document
coherence analysis.

Location: apps/api/src/coherence/adapters/persistence/pgvector_embedding_repository.py
"""

from __future__ import annotations

import logging
import time
from uuid import UUID

from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from ...ports.embedding_repository import (
    EmbeddingMatch,
    EmbeddingRecord,
    IEmbeddingRepository,
)

logger = logging.getLogger(__name__)


class PgvectorEmbeddingRepository(IEmbeddingRepository):
    """
    PostgreSQL + pgvector implementation of IEmbeddingRepository.

    Uses the clause_embeddings table with HNSW index for fast similarity search.
    All queries use native SQL functions (find_similar_clauses, find_cross_document_pairs)
    for optimal performance.

    IMPORTANT: SEC-009 Fix - All methods now verify tenant ownership via project.
    Tenant isolation is enforced by joining with projects table to verify tenant_id.

    Example usage:
        ```python
        async with get_db_session() as session:
            repo = PgvectorEmbeddingRepository(session, tenant_id=current_tenant_id)

            # Store embedding
            record = await repo.store_embedding(
                clause_id="BUD-001",
                project_id=project_id,
                embedding=embedding_vector,
                category="BUDGET",
                document_type="budget",
            )

            # Find similar clauses
            matches = await repo.find_similar(
                embedding=query_vector,
                project_id=project_id,
                top_k=10,
                similarity_threshold=0.85,
            )
        ```
    """

    def __init__(self, session: AsyncSession, tenant_id: UUID | None = None):
        """
        Initialize repository with a database session and optional tenant context.

        Args:
            session: SQLAlchemy async session
            tenant_id: Optional tenant ID for tenant isolation verification.
                      If provided, all operations will verify project ownership.
        """
        self.session = session
        self.tenant_id = tenant_id

    async def _verify_project_tenant(self, project_id: UUID) -> bool:
        """Verify that a project belongs to the current tenant."""
        from sqlalchemy import select

        from src.projects.adapters.persistence.models import ProjectORM

        stmt = select(ProjectORM.tenant_id).where(ProjectORM.id == project_id)
        result = await self.session.execute(stmt)
        project_tenant = result.scalar_one_or_none()
        if project_tenant is None:
            return False
        if self.tenant_id is None:
            return True
        return project_tenant == self.tenant_id

    async def store_embedding(
        self,
        *,
        clause_id: str,
        project_id: UUID,
        embedding: list[float],
        document_id: UUID | None = None,
        document_type: str = "other",
        text: str = "",
        category: str = "SCOPE",
        metadata: dict | None = None,
    ) -> EmbeddingRecord:
        """
        Store an embedding for a clause with tenant verification.

        Uses INSERT ... ON CONFLICT DO UPDATE to handle upserts efficiently.

        Args:
            clause_id: Unique identifier for the clause
            project_id: Project this clause belongs to
            embedding: Dense embedding vector (1536 dims for OpenAI ada-002/small)
            document_id: Optional source document identifier
            document_type: Type of source document
            text: Original clause text (will be truncated if > 1000 chars)
            category: Clause category (BUDGET, TIME, LEGAL, etc.)
            metadata: Additional structured data

        Returns:
            EmbeddingRecord with the stored embedding

        Raises:
            ValueError: If embedding dimension is invalid
            PermissionError: If project does not belong to current tenant
        """
        if self.tenant_id is not None:
            if not await self._verify_project_tenant(project_id):
                raise PermissionError("Cannot store embedding for project outside tenant")

        if len(embedding) != 1536:
            raise ValueError(
                f"Invalid embedding dimension: expected 1536, got {len(embedding)}"
            )

        # Truncate text if too long
        truncated_text = text[:1000] if len(text) > 1000 else text

        # Convert embedding to pgvector string format
        embedding_str = f"[{','.join(map(str, embedding))}]"

        # Prepare metadata
        meta = metadata or {}

        # Upsert using INSERT ... ON CONFLICT DO UPDATE
        sql_text(
            """INSERT INTO clause_embeddings
            (clause_id, project_id, document_id, document_type, text, embedding, category, metadata)
            VALUES (:clause_id, :project_id, :document_id, :document_type, :text,
                    :embedding::vector, :category, :metadata::jsonb)
            ON CONFLICT (clause_id, project_id)
            DO UPDATE SET
                document_id = EXCLUDED.document_id,
                document_type = EXCLUDED.document_type,
                text = EXCLUDED.text,
                embedding = EXCLUDED.embedding,
                category = EXCLUDED.category,
                metadata = EXCLUDED.metadata,
                created_at = now()
            RETURNING id, created_at"""
        )

        result = await self.session.execute(
            sql_text(
                """INSERT INTO clause_embeddings
                (clause_id, project_id, document_id, document_type, text, embedding, category, metadata)
                VALUES (:clause_id, :project_id, :document_id, :document_type, :text,
                        :embedding::vector, :category, :metadata::jsonb)
                ON CONFLICT (clause_id, project_id)
                DO UPDATE SET
                    document_id = EXCLUDED.document_id,
                    document_type = EXCLUDED.document_type,
                    text = EXCLUDED.text,
                    embedding = EXCLUDED.embedding,
                    category = EXCLUDED.category,
                    metadata = EXCLUDED.metadata,
                    created_at = now()
                RETURNING created_at"""
            ),
            {
                "clause_id": clause_id,
                "project_id": str(project_id),
                "document_id": str(document_id) if document_id else None,
                "document_type": document_type,
                "text": truncated_text,
                "embedding": embedding_str,
                "category": category,
                "metadata": meta,
            },
        )

        row = result.fetchone()
        created_at = row[0] if row else None

        await self.session.commit()

        logger.debug(
            f"Stored embedding for clause {clause_id} in project {project_id}"
        )

        return EmbeddingRecord(
            clause_id=clause_id,
            project_id=project_id,
            document_id=document_id,
            document_type=document_type,
            text=truncated_text,
            embedding=embedding,
            category=category,
            metadata=meta,
            created_at=created_at,
        )

    async def store_embeddings_batch(
        self,
        records: list[EmbeddingRecord],
    ) -> int:
        """
        Store multiple embeddings in a single batch operation with tenant verification.

        More efficient than calling store_embedding() multiple times.

        Args:
            records: List of EmbeddingRecord objects to store

        Returns:
            Number of records successfully stored

        Raises:
            PermissionError: If any project does not belong to current tenant
        """
        if not records:
            return 0

        if self.tenant_id is not None:
            for rec in records:
                if not await self._verify_project_tenant(rec.project_id):
                    raise PermissionError(
                        f"Cannot store embedding for project {rec.project_id} outside tenant"
                    )

        # Validate dimensions
        for rec in records:
            if len(rec.embedding) != 1536:
                raise ValueError(
                    f"Invalid embedding dimension for {rec.clause_id}: "
                    f"expected 1536, got {len(rec.embedding)}"
                )

        # Prepare batch insert
        values = []
        for rec in records:
            embedding_str = f"[{','.join(map(str, rec.embedding))}]"
            truncated_text = rec.text[:1000] if len(rec.text) > 1000 else rec.text

            values.append(
                {
                    "clause_id": rec.clause_id,
                    "project_id": str(rec.project_id),
                    "document_id": str(rec.document_id) if rec.document_id else None,
                    "document_type": rec.document_type,
                    "text": truncated_text,
                    "embedding": embedding_str,
                    "category": rec.category,
                    "metadata": rec.metadata,
                }
            )

        # Execute batch insert with ON CONFLICT DO NOTHING
        # (we could also use DO UPDATE for full upsert)
        stmt = sql_text(
            """INSERT INTO clause_embeddings
            (clause_id, project_id, document_id, document_type, text, embedding, category, metadata)
            VALUES (:clause_id, :project_id, :document_id, :document_type, :text,
                    :embedding::vector, :category, :metadata::jsonb)
            ON CONFLICT (clause_id, project_id) DO NOTHING"""
        )

        await self.session.execute(stmt, values)
        await self.session.commit()

        logger.info(f"Batch inserted {len(records)} embeddings")

        return len(records)

    async def find_similar(
        self,
        *,
        embedding: list[float],
        project_id: UUID,
        top_k: int = 10,
        similarity_threshold: float = 0.85,
        exclude_clause_ids: list[str] | None = None,
        filter_categories: list[str] | None = None,
        filter_document_types: list[str] | None = None,
    ) -> list[EmbeddingMatch]:
        """
        Find clauses similar to the given embedding with tenant verification.

        Uses the find_similar_clauses() PostgreSQL function with HNSW index
        for fast cosine similarity search.

        Args:
            embedding: Query embedding vector
            project_id: Project to search within
            top_k: Maximum number of matches to return
            similarity_threshold: Minimum similarity score (0.0-1.0)
            exclude_clause_ids: Clause IDs to exclude from results
            filter_categories: Only return matches from these categories
            filter_document_types: Only return matches from these document types

        Returns:
            List of EmbeddingMatch objects, sorted by similarity (descending)

        Raises:
            PermissionError: If project does not belong to current tenant
        """
        if self.tenant_id is not None:
            if not await self._verify_project_tenant(project_id):
                raise PermissionError("Cannot search embeddings for project outside tenant")

        if len(embedding) != 1536:
            raise ValueError(
                f"Invalid embedding dimension: expected 1536, got {len(embedding)}"
            )

        # Convert embedding to pgvector string format
        embedding_str = f"[{','.join(map(str, embedding))}]"

        # Call the find_similar_clauses function
        stmt = sql_text(
            """SELECT * FROM find_similar_clauses(
                :project_id::uuid,
                :embedding::vector,
                :similarity_threshold,
                :top_k,
                :filter_categories,
                :filter_document_types,
                :exclude_clause_ids
            )"""
        )

        result = await self.session.execute(
            stmt,
            {
                "project_id": str(project_id),
                "embedding": embedding_str,
                "similarity_threshold": similarity_threshold,
                "top_k": top_k,
                "filter_categories": filter_categories,
                "filter_document_types": filter_document_types,
                "exclude_clause_ids": exclude_clause_ids,
            },
        )

        matches: list[EmbeddingMatch] = []

        for row in result:
            # Row format from function:
            # (clause_id, document_id, document_type, text, category, metadata, similarity_score)
            matches.append(
                EmbeddingMatch(
                    source_clause_id="",  # Filled in by caller
                    target_clause_id=row[0],
                    target_project_id=project_id,
                    target_document_id=UUID(row[1]) if row[1] else None,
                    target_document_type=row[2],
                    target_text=row[3],
                    target_category=row[4],
                    similarity_score=float(row[6]),
                    match_reason="embedding_similarity",
                )
            )

        logger.debug(
            f"Found {len(matches)} similar clauses for project {project_id} "
            f"(threshold={similarity_threshold})"
        )

        return matches

    async def find_cross_document_pairs(
        self,
        *,
        project_id: UUID,
        similarity_threshold: float = 0.85,
        max_pairs: int = 20,
        categories_to_compare: list[tuple[str, str]] | None = None,
    ) -> list[EmbeddingMatch]:
        """
        Find similar clauses across different document types with tenant verification.

        Uses the find_cross_document_pairs() PostgreSQL function to efficiently
        find semantically related clauses from different documents.

        Args:
            project_id: Project to analyze
            similarity_threshold: Minimum similarity for a match
            max_pairs: Maximum number of pairs to return
            categories_to_compare: Specific category pairs to compare
                (not yet implemented in v1, returns all cross-document pairs)

        Returns:
            List of cross-document EmbeddingMatch pairs

        Raises:
            PermissionError: If project does not belong to current tenant
        """
        if self.tenant_id is not None:
            if not await self._verify_project_tenant(project_id):
                raise PermissionError("Cannot search embeddings for project outside tenant")

        start_time = time.time()

        # Call the find_cross_document_pairs function
        stmt = sql_text(
            """SELECT * FROM find_cross_document_pairs(
                :project_id::uuid,
                :similarity_threshold,
                :max_pairs
            )"""
        )

        result = await self.session.execute(
            stmt,
            {
                "project_id": str(project_id),
                "similarity_threshold": similarity_threshold,
                "max_pairs": max_pairs,
            },
        )

        matches: list[EmbeddingMatch] = []

        for row in result:
            # Row format from function:
            # (source_clause_id, target_clause_id, source_doc_type, target_doc_type,
            #  source_category, target_category, similarity_score)
            matches.append(
                EmbeddingMatch(
                    source_clause_id=row[0],
                    target_clause_id=row[1],
                    target_project_id=project_id,
                    target_document_id=None,  # Not returned by function
                    target_document_type=row[3],
                    target_text="",  # Not returned by function for efficiency
                    target_category=row[5],
                    similarity_score=float(row[6]),
                    match_reason="cross_document_similarity",
                )
            )

        elapsed_ms = (time.time() - start_time) * 1000

        logger.info(
            f"Found {len(matches)} cross-document pairs for project {project_id} "
            f"in {elapsed_ms:.2f}ms (threshold={similarity_threshold})"
        )

        return matches

    async def get_embedding(
        self,
        clause_id: str,
        project_id: UUID,
    ) -> EmbeddingRecord | None:
        """
        Get the stored embedding for a specific clause with tenant verification.

        Args:
            clause_id: The clause identifier
            project_id: Project the clause belongs to

        Returns:
            EmbeddingRecord or None if not found

        Raises:
            PermissionError: If project does not belong to current tenant
        """
        if self.tenant_id is not None:
            if not await self._verify_project_tenant(project_id):
                raise PermissionError("Cannot access embedding for project outside tenant")

        stmt = sql_text(
            """SELECT clause_id, project_id, document_id, document_type, text,
                      category, metadata, created_at
               FROM clause_embeddings
               WHERE clause_id = :clause_id AND project_id = :project_id"""
        )

        result = await self.session.execute(
            stmt,
            {"clause_id": clause_id, "project_id": str(project_id)},
        )

        row = result.fetchone()

        if not row:
            return None

        # Note: We don't fetch the embedding vector itself for efficiency
        # (it's 1536 floats = large payload)
        return EmbeddingRecord(
            clause_id=row[0],
            project_id=UUID(row[1]),
            document_id=UUID(row[2]) if row[2] else None,
            document_type=row[3],
            text=row[4],
            embedding=[],  # Not fetched
            category=row[5],
            metadata=row[6] or {},
            created_at=row[7],
        )

    async def delete_project_embeddings(
        self,
        project_id: UUID,
    ) -> int:
        """
        Delete all embeddings for a project with tenant verification.

        Used when a project is deleted or embeddings need to be regenerated.

        Args:
            project_id: Project whose embeddings to delete

        Returns:
            Number of embeddings deleted

        Raises:
            PermissionError: If project does not belong to current tenant
        """
        if self.tenant_id is not None:
            if not await self._verify_project_tenant(project_id):
                raise PermissionError("Cannot delete embeddings for project outside tenant")

        stmt = sql_text(
            """DELETE FROM clause_embeddings WHERE project_id = :project_id"""
        )

        result = await self.session.execute(
            stmt,
            {"project_id": str(project_id)},
        )

        await self.session.commit()

        count = result.rowcount or 0

        logger.info(f"Deleted {count} embeddings for project {project_id}")

        return count

    async def count_embeddings(
        self,
        project_id: UUID,
    ) -> int:
        """
        Count the number of stored embeddings for a project with tenant verification.

        Args:
            project_id: Project to count embeddings for

        Returns:
            Number of stored embeddings

        Raises:
            PermissionError: If project does not belong to current tenant
        """
        if self.tenant_id is not None:
            if not await self._verify_project_tenant(project_id):
                raise PermissionError("Cannot count embeddings for project outside tenant")

        stmt = sql_text(
            """SELECT COUNT(*) FROM clause_embeddings WHERE project_id = :project_id"""
        )

        result = await self.session.execute(
            stmt,
            {"project_id": str(project_id)},
        )

        row = result.fetchone()

        return row[0] if row else 0


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = ["PgvectorEmbeddingRepository"]
