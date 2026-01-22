"""
AI services and orchestration package.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .ai_service import AIService
    from .cost_controller import BudgetExceededException, CostControllerService

__all__ = ["AIService", "CostControllerService", "BudgetExceededException"]


def __getattr__(name: str):
    if name == "AIService":
        from .ai_service import AIService

        return AIService
    if name == "CostControllerService":
        from .cost_controller import CostControllerService

        return CostControllerService
    if name == "BudgetExceededException":
        from .cost_controller import BudgetExceededException

        return BudgetExceededException
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
