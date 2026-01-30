"""
Public contracts for Stakeholders module.

Expose only ports and application DTOs as public API.
"""
from src.stakeholders import ports
from src.stakeholders.application import dtos

__all__ = [
    "ports",
    "dtos",
]
