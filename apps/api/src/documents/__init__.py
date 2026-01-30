"""
Public contracts for Documents module.

Expose only ports and application DTOs as public API.
"""
from src.documents import ports
from src.documents.application import dtos

__all__ = [
    "ports",
    "dtos",
]
