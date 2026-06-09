"""
Pgvector implementation of the Centroid Repository.

Location: apps/api/src/coherence/adapters/persistence/pgvector_centroid_repository.py
"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.coherence.adapters.persistence.models import CategoryCentroidORM
from src.coherence.ports.centroid_repository import CategoryCentroidRecord, ICentroidRepository


class PgvectorCentroidRepository(ICentroidRepository):
    """
    PostgreSQL/pgvector implementation of ICentroidRepository.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_centroid(
        self, category: str, embedding_model: str, score_version: int
    ) -> CategoryCentroidRecord | None:
        """Fetch a centroid record by composite key."""
        stmt = select(CategoryCentroidORM).where(
            CategoryCentroidORM.category == category,
            CategoryCentroidORM.embedding_model == embedding_model,
            CategoryCentroidORM.score_version == score_version,
        )
        result = await self.session.execute(stmt)
        orm_record = result.scalar_one_or_none()

        if not orm_record:
            return None

        return CategoryCentroidRecord(
            id=orm_record.id,
            category=orm_record.category,
            embedding_model=orm_record.embedding_model,
            score_version=orm_record.score_version,
            embedding=orm_record.embedding,
            seed_hash=orm_record.seed_hash,
            created_at=orm_record.created_at,
        )

    async def save_centroid(self, record: CategoryCentroidRecord) -> CategoryCentroidRecord:
        """
        Upsert a centroid into pgvector.
        Uses PostgreSQL ON CONFLICT DO UPDATE to overwrite if a centroid
        already exists for the given category + model + version.
        """
        stmt = insert(CategoryCentroidORM).values(
            category=record.category,
            embedding_model=record.embedding_model,
            score_version=record.score_version,
            embedding=record.embedding,
            seed_hash=record.seed_hash,
        )

        # ON CONFLICT DO UPDATE
        upsert_stmt = stmt.on_conflict_do_update(
            constraint="uq_category_centroids_key",
            set_={
                "embedding": stmt.excluded.embedding,
                "seed_hash": stmt.excluded.seed_hash,
            },
        ).returning(CategoryCentroidORM)

        result = await self.session.execute(upsert_stmt)
        orm_record = result.scalar_one()

        return CategoryCentroidRecord(
            id=orm_record.id,
            category=orm_record.category,
            embedding_model=orm_record.embedding_model,
            score_version=orm_record.score_version,
            embedding=orm_record.embedding,
            seed_hash=orm_record.seed_hash,
            created_at=orm_record.created_at,
        )
