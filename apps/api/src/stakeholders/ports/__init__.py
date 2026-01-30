"""
Public ports (interfaces) for Stakeholders module.
"""
from src.stakeholders.ports.stakeholder_repository import IStakeholderRepository
from src.stakeholders.ports.raci_generator import RaciGeneratorPort

__all__ = [
    "IStakeholderRepository",
    "RaciGeneratorPort",
]
