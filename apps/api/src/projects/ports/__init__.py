"""
Ports (interfaces) for the Projects module.

These define the contracts that adapters must implement.
"""
from src.projects.ports.project_repository import ProjectRepository

__all__ = ["ProjectRepository"]
