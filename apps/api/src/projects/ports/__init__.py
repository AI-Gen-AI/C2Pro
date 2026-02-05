"""
Ports (interfaces) for the Projects module.

These define the contracts that adapters must implement.
"""
from src.projects.ports.project_repository import ProjectRepository
from src.projects.ports.wbs_query_port import IWBSQueryPort

__all__ = ["ProjectRepository", "IWBSQueryPort"]
