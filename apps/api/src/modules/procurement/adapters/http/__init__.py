"""
I9 Procurement HTTP Adapters
Test Suite ID: TS-I9-PROC-HTTP-001
"""

from src.modules.procurement.adapters.http.router import (
    get_procurement_planning_service,
    router,
)

__all__ = ["router", "get_procurement_planning_service"]

