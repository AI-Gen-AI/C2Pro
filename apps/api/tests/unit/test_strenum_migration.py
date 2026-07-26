"""TASK-DEV-030: behavioral contracts for the StrEnum migration."""

from enum import StrEnum

import pytest

from src.core.ai.ab_experiment import ExperimentStatus
from src.core.ai.llm_client import LLMErrorType
from src.core.ai.model_router import AITaskType, ModelTier
from src.core.ai.tools.metadata import ToolStatus
from src.core.ai.usage_analytics import AlertSeverity as AnalyticsAlertSeverity
from src.core.ai.usage_analytics import TimePeriod
from src.core.approval import ApprovalStatus
from src.core.auth.models import SubscriptionPlan, UserRole
from src.core.resilience.circuit_breaker import CircuitBreakerState
from src.core.tasks.celery_job_queue import JobStatus
from src.shared_kernel.enums import AlertSeverity, AlertStatus, AlertType, RACIRole, WBSItemType


@pytest.mark.parametrize(
    "enum_type",
    [
        ApprovalStatus,
        SubscriptionPlan,
        UserRole,
        CircuitBreakerState,
        JobStatus,
        AlertSeverity,
        AlertStatus,
        AlertType,
        RACIRole,
        WBSItemType,
        ExperimentStatus,
        LLMErrorType,
        AITaskType,
        ModelTier,
        ToolStatus,
        TimePeriod,
        AnalyticsAlertSeverity,
    ],
)
def test_shared_and_core_enums_are_strenum(enum_type: type[StrEnum]) -> None:
    """TS-UD-DEV-030-001: migrated enums retain value-based string contracts."""
    assert issubclass(enum_type, StrEnum)
    assert all(str(member) == member.value for member in enum_type)
