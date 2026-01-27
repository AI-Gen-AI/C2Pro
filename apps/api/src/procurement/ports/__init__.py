"""
Ports (interfaces) for the Procurement bounded context.
"""
from .wbs_repository import IWBSRepository
from .bom_repository import IBOMRepository

__all__ = [
    "IWBSRepository",
    "IBOMRepository",
]
