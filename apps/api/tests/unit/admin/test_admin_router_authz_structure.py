from fastapi.params import Depends

from src.admin.adapters.http import router as admin_router
from src.core.auth.platform_operator import require_platform_operator


def test_cross_tenant_admin_router_uses_only_platform_operator_authorization() -> None:
    dependency_calls = {
        dependency.dependency
        for dependency in admin_router.router.dependencies
        if isinstance(dependency, Depends)
    }

    assert require_platform_operator in dependency_calls
    assert not hasattr(admin_router, "require_admin_user")
    assert "get_current_user" not in admin_router.__dict__
    assert "UserRole" not in admin_router.__dict__


def test_retry_handler_accepts_tenantless_platform_operator() -> None:
    annotations = admin_router.retry_dlq_entry.__annotations__

    assert annotations["current_operator"] == "PlatformOperator"
