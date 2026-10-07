"""PC-2b.1 (#920): submit and approve resolve profile pins against the locked catalog (real PostgreSQL).

TS-UM-PC2B1-SUBMIT-002. A change set using a non-core decomposition_kind can be submitted only
when a profile owning that namespace is pinned by its published digest and declares the term.
Pins that do not resolve are violations; core-only change sets are unaffected.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.wbs.application.governed_change_service import AddNode, NodeSpec, WBSChangeSetInvalidError
from src.wbs.intelligence.profiles.catalog import default_catalog
from tests.modules.integration.test_pc2a1_wbs_governance_foundation import Scope, _scope
from tests.modules.integration.test_pc2a2_wbs_governed_apply import _cmd, _submit, _svc

pytestmark = pytest.mark.asyncio

SOLAR_PIN = default_catalog().get("solar_pv", "1.0.0").pin()


async def _draft(db: AsyncSession, s: Scope, *, pins: list[dict[str, Any]], kind: str | None) -> UUID:
    change_set = await _svc(db).create_change_set(project_id=s.project, tenant_id=s.tenant, actor=s.author,
                                                  title="PV plant", profile_refs=pins)
    change_set_id = change_set.id
    await db.commit()
    await _cmd(db, s, change_set_id, AddNode(NodeSpec("PV plant", "1", "control_account", kind)))
    return change_set_id


async def _violations(db: AsyncSession, s: Scope, change_set_id: UUID) -> list[str]:
    with pytest.raises(WBSChangeSetInvalidError) as caught:
        await _submit(db, s, change_set_id)
    await db.rollback()
    return list(caught.value.details["violations"])


async def test_an_unpinned_profile_namespace_blocks_submit(db: AsyncSession) -> None:
    s = await _scope(db)
    violations = await _violations(db, s, await _draft(db, s, pins=[], kind="solar_pv:block"))
    assert any("solar_pv" in v and "pinned" in v for v in violations)


async def test_a_pinned_declared_term_submits(db: AsyncSession) -> None:
    s = await _scope(db)
    digest = await _submit(db, s, await _draft(db, s, pins=[SOLAR_PIN], kind="solar_pv:block"))
    assert digest.startswith("sha256:")


async def test_an_undeclared_term_of_the_pinned_profile_blocks_submit(db: AsyncSession) -> None:
    s = await _scope(db)
    violations = await _violations(db, s, await _draft(db, s, pins=[SOLAR_PIN], kind="solar_pv:spaceship"))
    assert any("spaceship" in v for v in violations)


async def test_a_pin_that_is_not_the_published_digest_blocks_submit(db: AsyncSession) -> None:
    s = await _scope(db)
    forged = {**SOLAR_PIN, "profile_digest": "sha256:" + "0" * 64}
    violations = await _violations(db, s, await _draft(db, s, pins=[forged], kind="solar_pv:block"))
    assert any("profile pin" in v for v in violations)


async def test_core_only_change_sets_are_unaffected(db: AsyncSession) -> None:
    s = await _scope(db)
    digest = await _submit(db, s, await _draft(db, s, pins=[], kind="core:system"))
    assert digest.startswith("sha256:")
