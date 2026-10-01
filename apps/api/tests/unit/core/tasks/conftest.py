"""DB-less ingestion/analysis unit tests run against fake sessions.

#711: the real processing-authority SQL needs PostgreSQL, so these tests get
a permissive in-memory double scoped to ``ingestion_tasks`` only. The fence
itself is proven against a real database in
tests/integration/document_flow/test_711_processing_attempt_fence.py.
"""

from __future__ import annotations

import pytest

from tests.support.processing_authority_fakes import install_permissive_authority


@pytest.fixture(autouse=True)
def _permissive_processing_authority(monkeypatch: pytest.MonkeyPatch):
    return install_permissive_authority(monkeypatch)
