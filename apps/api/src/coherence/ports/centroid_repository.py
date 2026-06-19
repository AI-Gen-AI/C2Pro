"""
Centroid Repository Port for Coherence Engine Category Routing.

Location: apps/api/src/coherence/ports/centroid_repository.py
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class CategoryCentroidRecord:
    """
    A stored centroid vector for a specific category prototype.
    """

    category: str
    embedding_model: str
    score_version: int
    embedding: list[float] = field(default_factory=list)
    seed_hash: str = ""
    created_at: datetime | None = None
    id: UUID | None = None


class ICentroidRepository(ABC):
    """
    Repository interface for caching and retrieving Category Centroids.
    """

    @abstractmethod
    async def get_centroid(
        self, category: str, embedding_model: str, score_version: int
    ) -> CategoryCentroidRecord | None:
        """
        Retrieve a centroid by its unique composite key.
        Returns None if no matching centroid exists in the cache.
        """
        ...

    @abstractmethod
    async def save_centroid(self, record: CategoryCentroidRecord) -> CategoryCentroidRecord:
        """
        Save or update a centroid in the cache.
        """
        ...
