"""
Core Routers - Infrastructure HTTP endpoints

This module contains routers for infrastructure-related endpoints
that don't belong to a specific domain module.
"""

from src.core.routers.health import router as health_router

__all__ = ["health_router"]
