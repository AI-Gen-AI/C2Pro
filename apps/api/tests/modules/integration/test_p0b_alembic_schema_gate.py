"""Alembic-preserving integration gate for the real LangGraph HITL boundary.

Run only on a freshly migrated dedicated database. The alembic_schema marker
makes test_engine bypass reset_public_schema/Base.metadata.create_all.
"""
import pytest

from tests.modules.integration.test_p0b_true_langgraph_resume_hotfix import (
    real_saver as real_saver,  # noqa: F401 - pytest discovers the re-exported fixture
)
from tests.modules.integration.test_p0b_true_langgraph_resume_hotfix import (
    test_command_resume_consumes_interrupt_and_runs_downstream_once as _real_resume,
)

pytestmark = [pytest.mark.asyncio, pytest.mark.alembic_schema]


async def test_command_resume_on_migrated_schema(real_saver, db, test_user):
    await _real_resume(real_saver, db, test_user)
