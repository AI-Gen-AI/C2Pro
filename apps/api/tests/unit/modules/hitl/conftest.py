"""The HITL unit suites drive the review / resume code with hand-written fake sessions and repositories.

Those fakes have no ``tenants`` or ``project_review_grants`` tables, so the per-project authority (S5-02) cannot run
against them. These tests prove the MECHANICS (pins, ledger, leases, lineage), so the authorizer is replaced by a
permissive one here. The authority itself is proven with denials, on PostgreSQL, in
``tests/modules/integration/test_s5_project_review_authorization_pg.py`` -- never rely on this fixture for that.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from src.modules.hitl.application.project_review_authorization import ProjectReviewAuthorizer
from tests.modules.integration.hitl_actor import PermissiveProjectAuthorizer


@pytest.fixture(autouse=True)
def _permissive_project_authority(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    permissive = PermissiveProjectAuthorizer()
    monkeypatch.setattr(ProjectReviewAuthorizer, "require", type(permissive).require)
    monkeypatch.setattr(ProjectReviewAuthorizer, "for_repository", classmethod(lambda cls, _repository: permissive))
    yield
