"""
Analysis HTTP Adapters

HTTP routers for the analysis module.
"""

from src.analysis.adapters.http.router import router as analysis_router
from src.analysis.adapters.http.alerts_router import router as alerts_router

__all__ = ["analysis_router", "alerts_router"]
