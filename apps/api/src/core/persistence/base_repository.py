"""
Base repository contract.

Refers to Suite ID: TS-UAD-PER-REP-001.
"""


class BaseRepository:
    """Refers to Suite ID: TS-UAD-PER-REP-001."""

    def create(self, *_args, **_kwargs):
        raise NotImplementedError

    def get_by_id(self, *_args, **_kwargs):
        raise NotImplementedError

    def update(self, *_args, **_kwargs):
        raise NotImplementedError

    def delete(self, *_args, **_kwargs):
        raise NotImplementedError
