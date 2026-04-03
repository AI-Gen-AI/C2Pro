"""
TS-SEC-MOD-001: Security Models Presence Test

Verifies that AuditLogORM and AIUsageLogORM are defined and properly registered.
Refers to TASK-1474 and TASK-1478.
"""

import pytest
from src.core.database import Base

def test_audit_log_orm_presence():
    """Verifies that AuditLogORM is defined and registered with Base."""
    try:
        from src.core.security.adapters.persistence.models import AuditLogORM
        assert AuditLogORM.__tablename__ == "audit_logs"
        assert "audit_logs" in Base.metadata.tables
    except ImportError:
        pytest.fail("AuditLogORM could not be imported from src.core.security.adapters.persistence.models")
    except AttributeError:
        pytest.fail("AuditLogORM does not have a __tablename__ attribute")

def test_ai_usage_log_orm_presence():
    """
    Verifies that AIUsageLogORM is defined and registered with Base.
    Expected to fail until TASK-1478 is implemented.
    """
    try:
        # This path might change based on implementation
        from src.core.ai.models import AIUsageLogORM
        assert AIUsageLogORM.__tablename__ == "ai_usage_logs"
        assert "ai_usage_logs" in Base.metadata.tables
    except ImportError:
        pytest.fail("AIUsageLogORM could not be imported. Implement it in src.core.ai.models.")
    except Exception as e:
        pytest.fail(f"AIUsageLogORM check failed: {e}")
