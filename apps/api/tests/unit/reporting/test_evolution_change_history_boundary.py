"""TS-P0D-REPORT-006 - Evolution Report document change history boundary.

Reporting consumes computed revision change sets through a port. Until a readable
change-set store exists, the default source must say it is unavailable; it must
never return an empty history that would read as "nothing changed".
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.reporting.adapters.sources.unavailable_document_change_history import (
    DOCUMENT_CHANGE_HISTORY_UNAVAILABLE_REASON,
    UnavailableDocumentChangeHistory,
)
from src.reporting.application.evolution_ports import DocumentChangeHistory
from src.reporting.application.ports import SourceUnavailableError


async def test_default_change_history_is_unavailable_not_empty() -> None:
    history: DocumentChangeHistory = UnavailableDocumentChangeHistory()
    with pytest.raises(SourceUnavailableError) as raised:
        await history.list_revision_changes(uuid4(), uuid4(), from_event_id=uuid4(), to_event_id=uuid4())
    assert raised.value.reason == DOCUMENT_CHANGE_HISTORY_UNAVAILABLE_REASON


def test_unavailable_reason_is_user_facing() -> None:
    reason = DOCUMENT_CHANGE_HISTORY_UNAVAILABLE_REASON
    assert reason.startswith("Document change history is not available yet")
    for internal_term in ("P0c", "ADR", "Error", "change_set", "None"):
        assert internal_term not in reason
