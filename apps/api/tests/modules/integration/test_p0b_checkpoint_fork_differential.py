"""Real PostgreSQL differential for LangGraph HITL checkpoint fork semantics."""
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.auth.models import User, Tenant
from tests.modules.integration.test_p0b_true_langgraph_resume_hotfix import (
    _build_real_graph,
    _run_to_interrupt,
    _seed,
    real_saver,  # noqa: F401 - pytest fixture re-export
)
pytestmark = pytest.mark.asyncio

async def test_aupdate_state_fork_loses_interrupt_but_original_preserves_it(
    real_saver, db: AsyncSession, test_user: User
) -> None:
    """Differential: aupdate_state loses the interrupt; original preserves it.

    Use the same real production node, LangGraph and PostgreSQL saver as the
    green original-checkpoint resume tests; no mock of aupdate_state.
    """
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    document = await _seed(db, tenant)
    thread_id = register(f"document:{document.id}:fork-differential")
    app = _build_real_graph(saver)
    cfg, original_id = await _run_to_interrupt(app, document, tenant, thread_id, db=db)
    original = await app.aget_state({"configurable": {"thread_id": thread_id, "checkpoint_id": original_id}})
    assert original.next == ("human_interrupt",), (original.next, original.tasks)
    assert any(task.interrupts for task in original.tasks)

    fork_cfg = await app.aupdate_state(
        original.config,
        {"resume_provenance": {"operation_id": str(uuid.uuid4()), "attempt_id": str(uuid.uuid4()),
                               "fencing_token": 1, "decision_revision": 1}},
    )
    fork = await app.aget_state(fork_cfg)
    assert fork.config["configurable"]["thread_id"] == thread_id
    assert fork.config["configurable"]["checkpoint_id"] != original_id
    assert fork.next == original.next, (
        f"FORK_LOST_INTERRUPTED_TASK: original.next={original.next}, "
        f"fork.next={fork.next}, original.tasks={original.tasks}, fork.tasks={fork.tasks}, "
        f"fork.metadata={fork.metadata}"
    )
    assert not any(task.interrupts for task in fork.tasks), (
        f"LANGGRAPH_FORK_BEHAVIOR_CHANGED: fork.next={fork.next}, tasks={fork.tasks}"
    )
    original_again = await app.aget_state(original.config)
    assert any(task.interrupts for task in original_again.tasks)
