"""
Generic Repository Base Class Tests (TDD - RED Phase)

Refers to Suite ID: TS-UAD-PER-REP-001.
"""

from __future__ import annotations

import pytest

from src.core.persistence.base_repository import BaseRepository


class TestBaseRepositoryContract:
    """Refers to Suite ID: TS-UAD-PER-REP-001."""

    def test_base_repository_requires_crud_overrides(self):
        class DummyRepo(BaseRepository):
            pass

        repo = DummyRepo()

        with pytest.raises(NotImplementedError):
            repo.create(None)

        with pytest.raises(NotImplementedError):
            repo.get_by_id(None)

        with pytest.raises(NotImplementedError):
            repo.update(None, None)

        with pytest.raises(NotImplementedError):
            repo.delete(None)
