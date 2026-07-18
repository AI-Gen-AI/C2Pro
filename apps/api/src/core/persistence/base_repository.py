"""
Base repository contract.

Refers to Suite ID: TS-UAD-PER-REP-001.
"""
from typing import Any


class BaseRepository:
    """Refers to Suite ID: TS-UAD-PER-REP-001."""

    def create(self, *_args: Any, **_kwargs: Any) -> Any:
        raise NotImplementedError

    def get_by_id(self, *_args: Any, **_kwargs: Any) -> Any:
        raise NotImplementedError

    def update(self, *_args: Any, **_kwargs: Any) -> Any:
        raise NotImplementedError

    def delete(self, *_args: Any, **_kwargs: Any) -> Any:
        raise NotImplementedError
