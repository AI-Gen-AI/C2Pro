"""Deprecated compatibility module for cost controller imports.

Use ``src.core.ai.cost_controller`` directly in new code.
"""

from src.core.ai.cost_controller import BudgetExceededException, CostControllerService

__all__ = ["BudgetExceededException", "CostControllerService"]
