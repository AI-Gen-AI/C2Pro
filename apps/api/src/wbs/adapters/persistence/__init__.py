"""WBS persistence adapters."""

from src.wbs.adapters.persistence.in_memory_repository import (
    InMemoryWBSRepository,
    get_wbs_repository,
)

__all__ = ["InMemoryWBSRepository", "get_wbs_repository"]
