"""A budget's declared total and denominations, bound to the revision that declared them.

``documents.document_metadata`` is one mutable blob per document: the ingestion of a proposed
re-upload must not overwrite what the accepted revision declared, and a reader must not take "the
latest ingested" for "the approved one". The declaration is therefore stored per revision, as one
inseparable entry (total + currencies + the revision's identity), keyed by ``revision_id``. The
coherence reader selects the entry of the trusted-current revision (the same C3a authority the
contract totals use) and ignores the rest. A revision that declares no total records that
explicitly, so a later approval of it yields UNKNOWN instead of inheriting an older revision's
figure. The legacy unstamped ``stated_total`` / ``stated_total_currencies`` keys carry no
provenance: writers remove them and no reader consumes them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from src.documents.domain.revision_declarations import STATED_TOTAL_BY_REVISION_KEY

_LEGACY_KEYS = ("stated_total", "stated_total_currencies")


def record_revision_stated_total(
    metadata: dict[str, Any],
    *,
    revision_id: UUID | str | None,
    blob_hash: str | None,
    total: float | int | None,
    currencies: Sequence[str] | None,
) -> None:
    """Record this revision's declaration in ``metadata`` (in place), keeping other revisions'.

    Without a pinned revision there is no identity to bind the figure to: nothing is recorded
    (readers then report no declared total) rather than an unstamped value.
    """
    for legacy in _LEGACY_KEYS:
        metadata.pop(legacy, None)
    if revision_id is None:
        return
    existing = metadata.get(STATED_TOTAL_BY_REVISION_KEY)
    entries: dict[str, Any] = dict(existing) if isinstance(existing, Mapping) else {}
    entries[str(revision_id)] = {
        "revision_id": str(revision_id),
        "blob_hash": blob_hash,
        "total": total,
        "currencies": list(currencies) if currencies and total is not None else [],
    }
    metadata[STATED_TOTAL_BY_REVISION_KEY] = entries


__all__ = ["STATED_TOTAL_BY_REVISION_KEY", "record_revision_stated_total"]
